from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """Domain error rendered as the spec's {error: {code, message}} envelope."""

    def __init__(self, status_code: int, code: str, message: str, **extra: object):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra
        super().__init__(message)


def error_body(code: str, message: str, **extra: object) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if extra:
        body["error"].update(extra)
    return body


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, **exc.extra),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "unauthenticated",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            429: "rate_limited",
        }.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            # jsonable_encoder: custom-validator errors carry the raw exception
            # in ctx, which json.dumps cannot serialise.
            content=error_body(
                "validation_error", "Invalid request", details=jsonable_encoder(exc.errors())
            ),
        )
