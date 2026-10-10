from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from manual_assistant.presentation.http.dependencies import UseCases
from manual_assistant.presentation.http.errors import register_error_handlers
from manual_assistant.presentation.http.routers import (
    auth,
    conversations,
    health,
    manuals,
    questions,
    users,
)

API_PREFIX = "/api/v1"

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_http_app(
    *,
    title: str,
    version: str,
    cors_origins: Sequence[str],
    use_cases: UseCases,
    cookie_secure: bool = False,
    lifespan: Lifespan | None = None,
) -> FastAPI:
    app = FastAPI(
        title=title,
        version=version,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.use_cases = use_cases
    app.state.cookie_secure = cookie_secure

    # O frontend roda em outra origem (XAMPP), então o navegador exige CORS.
    # allow_credentials: o cookie de sessão precisa acompanhar as requisições do frontend.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(users.router, prefix=API_PREFIX)
    app.include_router(manuals.router, prefix=API_PREFIX)
    app.include_router(questions.router, prefix=API_PREFIX)
    app.include_router(conversations.router, prefix=API_PREFIX)
    return app
