import logging
import traceback

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger("superbizagent")


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.error(
                "unhandled_error",
                extra={
                    "path": str(request.url),
                    "method": request.method,
                    "traceback": traceback.format_exc(),
                },
            )
            detail = "internal server error"
            if settings.app_env == "dev":
                detail = traceback.format_exc()
            return JSONResponse(status_code=500, content={"detail": detail})
