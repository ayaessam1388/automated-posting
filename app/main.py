"""FastAPI entry point: POST /posting publishes a message to every configured platform."""

import logging
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.platforms import build_platforms
from app.platforms.base import Platform
from app.schemas import ErrorResponse, PostingRequest, PostingResponse, ValidationErrorItem
from app.services.posting_service import post_everywhere

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        app.state.http_client = client
        yield


app = FastAPI(
    title="Automated Multi-Platform Posting",
    description="Publishes one short message with a CTA link to several third-party platforms at once.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"] if part != "body") or "body"
        ctx_error = error.get("ctx", {}).get("error")
        message = str(ctx_error) if isinstance(ctx_error, ValueError) else error["msg"]
        errors.append(ValidationErrorItem(field=field, message=message))
    return JSONResponse(status_code=422, content=ErrorResponse(errors=errors).model_dump())


def get_platforms(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> list[Platform]:
    return build_platforms(settings, request.app.state.http_client)


@app.post(
    "/posting",
    response_model=PostingResponse,
    responses={422: {"model": ErrorResponse, "description": "Invalid message"}},
    summary="Publish a message to all platforms",
)
async def create_posting(
    payload: PostingRequest, platforms: Annotated[list[Platform], Depends(get_platforms)]
) -> PostingResponse:
    return await post_everywhere(platforms, payload.message, payload.link)


@app.get("/health", summary="Liveness check")
async def health() -> dict[str, str]:
    return {"status": "ok"}
