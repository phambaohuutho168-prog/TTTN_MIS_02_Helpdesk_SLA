import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import error_response


logger = logging.getLogger(__name__)


_VALIDATION_MESSAGES = {
    "missing": "Trường dữ liệu là bắt buộc.",
    "extra_forbidden": "Trường dữ liệu không được hỗ trợ.",
    "int_parsing": "Giá trị phải là số nguyên hợp lệ.",
    "float_parsing": "Giá trị phải là số hợp lệ.",
    "bool_parsing": "Giá trị phải là true hoặc false.",
    "date_from_datetime_parsing": "Ngày không đúng định dạng ISO 8601.",
    "datetime_from_date_parsing": "Thời gian không đúng định dạng ISO 8601.",
    "json_invalid": "Nội dung JSON không hợp lệ.",
    "literal_error": "Giá trị không thuộc tập được cho phép.",
}


def _validation_field(error: dict[str, Any]) -> str | None:
    location = list(error.get("loc", ()))
    if location and location[0] in {"body", "query", "path", "header", "cookie"}:
        location.pop(0)
    if not location:
        return "body" if error.get("type") == "json_invalid" else None
    return ".".join(str(part) for part in location)


def _validation_message(error: dict[str, Any]) -> str:
    error_type = str(error.get("type", ""))
    if error_type in _VALIDATION_MESSAGES:
        return _VALIDATION_MESSAGES[error_type]

    context = error.get("ctx") or {}
    if error_type == "string_too_short":
        return f"Nội dung phải có ít nhất {context.get('min_length')} ký tự."
    if error_type == "string_too_long":
        return f"Nội dung không được vượt quá {context.get('max_length')} ký tự."
    if error_type == "greater_than":
        return f"Giá trị phải lớn hơn {context.get('gt')}."
    if error_type == "greater_than_equal":
        return f"Giá trị phải lớn hơn hoặc bằng {context.get('ge')}."
    if error_type == "less_than_equal":
        return f"Giá trị phải nhỏ hơn hoặc bằng {context.get('le')}."
    return str(error.get("msg") or "Dữ liệu không hợp lệ.")


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        errors: list[dict[str, str | None]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.errors = errors or []
        self.headers = headers or {}
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        if exc.code.startswith("AUTH_") or exc.code == "RATE_LIMIT_EXCEEDED":
            logger.warning(
                "authentication_event request_id=%s code=%s status=%s",
                getattr(request.state, "request_id", "unknown"),
                exc.code,
                exc.status_code,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                request,
                code=exc.code,
                message=exc.message,
                errors=exc.errors,
            ),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors: list[dict[str, str | None]] = []
        for error in exc.errors():
            errors.append(
                {
                    "field": _validation_field(error),
                    "message": _validation_message(error),
                }
            )
        return JSONResponse(
            status_code=422,
            content=error_response(
                request,
                code="VALIDATION_ERROR",
                message="Dữ liệu yêu cầu không hợp lệ.",
                errors=errors,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        known_errors = {
            404: ("ROUTE_NOT_FOUND", "Không tìm thấy endpoint được yêu cầu."),
            405: (
                "METHOD_NOT_ALLOWED",
                "Phương thức HTTP không được hỗ trợ cho endpoint này.",
            ),
            413: ("PAYLOAD_TOO_LARGE", "Dữ liệu gửi lên vượt quá giới hạn cho phép."),
        }
        code, message = known_errors.get(
            exc.status_code,
            ("HTTP_ERROR", str(exc.detail)),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                request,
                code=code,
                message=message,
            ),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled error request_id=%s",
            getattr(request.state, "request_id", "unknown"),
        )
        return JSONResponse(
            status_code=500,
            content=error_response(
                request,
                code="INTERNAL_SERVER_ERROR",
                message="Hệ thống gặp lỗi không mong đợi.",
            ),
        )
