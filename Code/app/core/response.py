from datetime import datetime, timezone
from typing import Any

from fastapi import Request


def response_meta(request: Request) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "request_id": getattr(request.state, "request_id", "unknown"),
        "timestamp": timestamp,
    }


def success_response(
    request: Request,
    *,
    data: Any,
    message: str,
    code: str = "SUCCESS",
) -> dict[str, Any]:
    return {
        "success": True,
        "code": code,
        "message": message,
        "data": data,
        "meta": response_meta(request),
    }


def error_response(
    request: Request,
    *,
    code: str,
    message: str,
    errors: list[dict[str, str | None]] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "code": code,
        "message": message,
        "errors": errors or [],
        "meta": response_meta(request),
    }
