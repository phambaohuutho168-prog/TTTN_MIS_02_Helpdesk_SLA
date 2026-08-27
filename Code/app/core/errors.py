import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.response import error_response


logger = logging.getLogger(__name__)


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
            location = ".".join(str(part) for part in error.get("loc", [])[1:])
            errors.append(
                {
                    "field": location or None,
                    "message": error.get("msg", "Dữ liệu không hợp lệ."),
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

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                request,
                code="HTTP_ERROR",
                message=str(exc.detail),
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
