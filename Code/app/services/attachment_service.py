from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.rbac import RoleCode
from app.models.attachment import Attachment
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories import attachment_repository, ticket_repository
from app.schemas.attachment import AttachmentResponse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_MIME_BY_EXTENSION: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@dataclass(frozen=True)
class StoredUpload:
    original_name: str
    object_key: str
    absolute_path: Path
    mime_type: str
    size: int


def _storage_root() -> Path:
    configured = Path(settings.ATTACHMENT_STORAGE_DIR).expanduser()
    root = configured if configured.is_absolute() else PROJECT_ROOT / configured
    return root.resolve()


def _remove_directory_if_empty(directory: Path) -> None:
    try:
        directory.rmdir()
    except (FileNotFoundError, OSError):
        pass


def _safe_original_name(filename: str | None) -> tuple[str, str]:
    normalized = (filename or "").replace("\\", "/")
    name = PurePosixPath(normalized).name.strip()
    suffix = Path(name).suffix.lower()
    if (
        not name
        or name in {".", ".."}
        or "\x00" in name
        or len(name) > 255
        or suffix not in ALLOWED_MIME_BY_EXTENSION
    ):
        raise AppError(
            415,
            "ATTACHMENT_TYPE_NOT_ALLOWED",
            "Tên tệp hoặc phần mở rộng không thuộc danh sách cho phép.",
        )
    return name, suffix


def _copy_upload_to_temp(source, temp_path: Path, max_bytes: int) -> int:
    size = 0
    source.seek(0)
    try:
        with temp_path.open("xb") as target:
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise AppError(
                        413,
                        "ATTACHMENT_SIZE_EXCEEDED",
                        f"Tệp vượt quá giới hạn {settings.MAX_ATTACHMENT_SIZE_MB} MB.",
                    )
                target.write(chunk)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    if size == 0:
        temp_path.unlink(missing_ok=True)
        raise AppError(
            415,
            "ATTACHMENT_TYPE_NOT_ALLOWED",
            "Không chấp nhận tệp rỗng.",
        )
    return size


def _detect_mime(path: Path, suffix: str) -> str | None:
    with path.open("rb") as source:
        header = source.read(16)

    if suffix == ".pdf" and header.startswith(b"%PDF-"):
        return "application/pdf"
    if suffix == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if suffix in {".jpg", ".jpeg"} and header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if suffix == ".txt":
        try:
            content = path.read_bytes()
            content.decode("utf-8")
        except UnicodeDecodeError:
            return None
        if b"\x00" not in content:
            return "text/plain"
        return None
    if suffix in {".docx", ".xlsx"}:
        try:
            with ZipFile(path) as archive:
                names = set(archive.namelist())
        except BadZipFile:
            return None
        if "[Content_Types].xml" not in names:
            return None
        if suffix == ".docx" and any(name.startswith("word/") for name in names):
            return ALLOWED_MIME_BY_EXTENSION[suffix]
        if suffix == ".xlsx" and any(name.startswith("xl/") for name in names):
            return ALLOWED_MIME_BY_EXTENSION[suffix]
    return None


def _validate_and_finalize_upload(
    upload: UploadFile,
    *,
    ticket_id: int,
) -> StoredUpload:
    original_name, suffix = _safe_original_name(upload.filename)
    declared_mime = (upload.content_type or "").split(";", 1)[0].strip().lower()
    expected_mime = ALLOWED_MIME_BY_EXTENSION[suffix]
    if declared_mime != expected_mime:
        raise AppError(
            415,
            "ATTACHMENT_TYPE_NOT_ALLOWED",
            "MIME khai báo không phù hợp với phần mở rộng của tệp.",
        )

    root = _storage_root()
    ticket_directory = root / str(ticket_id)
    ticket_directory.mkdir(parents=True, exist_ok=True)
    temp_path = ticket_directory / f".{uuid4().hex}.uploading"
    max_bytes = settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    try:
        size = _copy_upload_to_temp(upload.file, temp_path, max_bytes)
    except Exception:
        _remove_directory_if_empty(ticket_directory)
        raise

    detected_mime = _detect_mime(temp_path, suffix)
    if detected_mime != expected_mime:
        temp_path.unlink(missing_ok=True)
        _remove_directory_if_empty(ticket_directory)
        raise AppError(
            415,
            "ATTACHMENT_TYPE_NOT_ALLOWED",
            "Nội dung thực của tệp không phù hợp MIME hoặc phần mở rộng.",
        )

    object_key = (Path(str(ticket_id)) / f"{uuid4().hex}{suffix}").as_posix()
    final_path = (root / object_key).resolve()
    try:
        final_path.relative_to(root)
    except ValueError as exc:
        temp_path.unlink(missing_ok=True)
        _remove_directory_if_empty(ticket_directory)
        raise AppError(500, "ATTACHMENT_STORAGE_ERROR", "Đường dẫn lưu tệp không hợp lệ.") from exc
    temp_path.replace(final_path)
    return StoredUpload(
        original_name=original_name,
        object_key=object_key,
        absolute_path=final_path,
        mime_type=detected_mime,
        size=size,
    )


def _is_admin(user: User) -> bool:
    return RoleCode.ADMIN.value in user.role_codes


def _assert_ticket_scope(ticket: Ticket, user: User) -> None:
    if ticket.requester_id == user.user_id or _is_admin(user):
        return
    if RoleCode.PROCESSOR.value in user.role_codes and any(
        assignment.is_current and assignment.assignee_id == user.user_id
        for assignment in ticket.assignments
    ):
        return
    raise AppError(
        403,
        "TICKET_ACCESS_DENIED",
        "Bạn không thuộc phạm vi sở hữu hoặc phân công của ticket.",
    )


def _assert_internal_comment_scope(attachment: Attachment, user: User) -> None:
    if attachment.comment is None or attachment.comment.visibility != "INTERNAL":
        return
    if _is_admin(user) or RoleCode.PROCESSOR.value in user.role_codes:
        return
    raise AppError(
        403,
        "TICKET_ACCESS_DENIED",
        "Bạn không có quyền truy cập tệp của trao đổi nội bộ.",
    )


async def upload_attachment(
    session: AsyncSession,
    *,
    ticket_id: int,
    comment_id: int | None,
    uploader: User,
    upload: UploadFile,
) -> AttachmentResponse:
    ticket = await ticket_repository.get_ticket_by_id(session, ticket_id)
    if ticket is None:
        raise AppError(404, "TICKET_NOT_FOUND", "Không tìm thấy ticket.")
    _assert_ticket_scope(ticket, uploader)
    if ticket.current_status.is_terminal:
        raise AppError(
            409,
            "TICKET_ALREADY_TERMINAL",
            "Ticket đã kết thúc nên không nhận thêm tệp đính kèm.",
        )

    if comment_id is not None:
        comment = await attachment_repository.get_comment_by_id(session, comment_id)
        if comment is None or comment.ticket_id != ticket_id:
            raise AppError(
                409,
                "COMMENT_TICKET_MISMATCH",
                "Comment không tồn tại hoặc không thuộc ticket này.",
            )
        if comment.visibility == "INTERNAL" and not (
            _is_admin(uploader)
            or RoleCode.PROCESSOR.value in uploader.role_codes
        ):
            raise AppError(
                403,
                "TICKET_ACCESS_DENIED",
                "Requester không được gắn tệp vào trao đổi nội bộ.",
            )

    stored = await run_in_threadpool(
        _validate_and_finalize_upload,
        upload,
        ticket_id=ticket_id,
    )
    try:
        attachment = await attachment_repository.create_attachment_record(
            session,
            ticket_id=ticket_id,
            comment_id=comment_id,
            uploaded_by=uploader.user_id,
            file_name=stored.original_name,
            storage_path=stored.object_key,
            mime_type=stored.mime_type,
            file_size=stored.size,
        )
        await session.commit()
    except SQLAlchemyError as exc:
        await session.rollback()
        stored.absolute_path.unlink(missing_ok=True)
        _remove_directory_if_empty(stored.absolute_path.parent)
        raise AppError(
            409,
            "ATTACHMENT_STORAGE_CONFLICT",
            "Không thể lưu metadata tệp đính kèm.",
        ) from exc
    created = await attachment_repository.get_attachment_by_id(
        session,
        attachment.attachment_id,
    )
    if created is None:
        stored.absolute_path.unlink(missing_ok=True)
        _remove_directory_if_empty(stored.absolute_path.parent)
        raise AppError(500, "INTERNAL_SERVER_ERROR", "Không thể tải tệp vừa tạo.")
    return AttachmentResponse.model_validate(created)


async def get_attachment_for_download(
    session: AsyncSession,
    *,
    attachment_id: int,
    user: User,
) -> tuple[Attachment, Path]:
    attachment = await attachment_repository.get_attachment_by_id(
        session,
        attachment_id,
    )
    if attachment is None:
        raise AppError(404, "ATTACHMENT_NOT_FOUND", "Không tồn tại tệp đính kèm.")
    _assert_ticket_scope(attachment.ticket, user)
    _assert_internal_comment_scope(attachment, user)
    path = (_storage_root() / attachment.storage_path).resolve()
    try:
        path.relative_to(_storage_root())
    except ValueError as exc:
        raise AppError(404, "ATTACHMENT_NOT_FOUND", "Không tồn tại tệp đính kèm.") from exc
    if not path.is_file():
        raise AppError(404, "ATTACHMENT_NOT_FOUND", "Không tồn tại tệp đính kèm.")
    return attachment, path


async def delete_attachment(
    session: AsyncSession,
    *,
    attachment_id: int,
    user: User,
) -> None:
    attachment = await attachment_repository.get_attachment_by_id(
        session,
        attachment_id,
    )
    if attachment is None:
        raise AppError(404, "ATTACHMENT_NOT_FOUND", "Không tồn tại tệp đính kèm.")
    try:
        _assert_ticket_scope(attachment.ticket, user)
    except AppError as exc:
        if exc.code != "TICKET_ACCESS_DENIED":
            raise
        raise AppError(
            403,
            "ATTACHMENT_DELETE_FORBIDDEN",
            "Bạn không có quyền xóa tệp đính kèm này.",
        ) from exc
    if not _is_admin(user) and (
        attachment.uploaded_by != user.user_id
        or attachment.ticket.current_status.is_terminal
    ):
        raise AppError(
            403,
            "ATTACHMENT_DELETE_FORBIDDEN",
            "Bạn không có quyền xóa tệp này hoặc ticket đã kết thúc.",
        )

    path = (_storage_root() / attachment.storage_path).resolve()
    try:
        path.relative_to(_storage_root())
    except ValueError:
        path = Path()
    await attachment_repository.delete_attachment_record(session, attachment)
    await session.commit()
    if path.is_file():
        await run_in_threadpool(path.unlink)
        await run_in_threadpool(_remove_directory_if_empty, path.parent)
