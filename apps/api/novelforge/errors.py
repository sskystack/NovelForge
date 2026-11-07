from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class Problem(Exception):
    def __init__(self, status: int, code: str, title: str, detail: str) -> None:
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail


def problem_response(
    request: Request,
    status: int,
    code: str,
    title: str,
    detail: str,
    extra: dict | None = None,
) -> JSONResponse:
    content = {
        "type": f"https://novelforge.dev/problems/{code.lower().replace('_', '-')}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "request_id": getattr(request.state, "request_id", ""),
    }
    if extra:
        content.update(extra)
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        headers={"X-Request-ID": content["request_id"]},
        content=content,
    )


async def problem_handler(request: Request, error: Problem) -> JSONResponse:
    return problem_response(request, error.status, error.code, error.title, error.detail)


async def validation_error_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    errors = [
        {"location": list(item["loc"]), "message": item["msg"], "code": item["type"]}
        for item in error.errors()
    ]
    return problem_response(
        request,
        422,
        "INVALID_REQUEST",
        "Request validation failed",
        "One or more request fields are invalid.",
        {"errors": errors},
    )


async def http_error_handler(request: Request, error: StarletteHTTPException) -> JSONResponse:
    titles = {404: "Resource not found", 405: "Method not allowed"}
    return problem_response(
        request,
        error.status_code,
        "HTTP_ERROR",
        titles.get(error.status_code, "Request failed"),
        str(error.detail),
    )
