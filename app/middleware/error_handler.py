"""Global exception handler — sanitized in prod, full traceback in dev."""

import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings

logger = logging.getLogger("superbizagent")


async def global_exception_handler(request: Request, exc: Exception):
    # Let Starlette/FastAPI handle HTTPExceptions natively
    if isinstance(exc, StarletteHTTPException):
        raise exc

    logger.error(
        "unhandled_error",
        extra={
            "path": str(request.url),
            "method": request.method,
            "error": repr(exc),
        },
    )

    if settings.app_env == "dev":
        detail = traceback.format_exc()
    else:
        detail = "internal server error"

    return JSONResponse(status_code=500, content={"detail": detail})
