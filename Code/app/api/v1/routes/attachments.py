from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import AnyBusinessRoleContext
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.attachment import AttachmentResponse
from app.schemas.common import SuccessResponse
from app.services import attachment_service


router = APIRouter(tags=["Attachments"])


@router.post(
    "/tickets/{ticket_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[AttachmentResponse],
    summary="ATT-01 - Tải tệp lên ticket hoặc comment",
)
async def upload_attachment(
    request: Request,
    ticket_id: int,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(description="Tệp minh chứng")],
    comment_id: Annotated[int | None, Form(ge=1)] = None,
):
    data = await attachment_service.upload_attachment(
        session,
        ticket_id=ticket_id,
        comment_id=comment_id,
        uploader=context.user,
        upload=file,
    )
    return success_response(
        request,
        data=data,
        code="ATTACHMENT_CREATED",
        message="Tải tệp đính kèm thành công.",
    )


@router.get(
    "/attachments/{attachment_id}/download",
    response_class=FileResponse,
    summary="ATT-02 - Tải tệp đính kèm có kiểm soát",
    responses={
        200: {
            "content": {"application/octet-stream": {}},
            "description": "Nội dung tệp đính kèm.",
        }
    },
)
async def download_attachment(
    attachment_id: int,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    attachment, path = await attachment_service.get_attachment_for_download(
        session,
        attachment_id=attachment_id,
        user=context.user,
    )
    return FileResponse(
        path=path,
        media_type=attachment.mime_type,
        filename=attachment.file_name,
        content_disposition_type="attachment",
    )


@router.delete(
    "/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="ATT-03 - Xóa tệp đính kèm",
)
async def delete_attachment(
    attachment_id: int,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await attachment_service.delete_attachment(
        session,
        attachment_id=attachment_id,
        user=context.user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
