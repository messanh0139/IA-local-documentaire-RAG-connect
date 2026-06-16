from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
# Ensure all models are imported so SQLAlchemy can resolve relationship strings at startup
from app.models import audit_log, chat_message, connector, conversation, document, group, sync_run, tenant, user  # noqa: F401
from app.core.exceptions import install_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import request_context_middleware, security_headers_middleware


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.app_env == "dev",
        docs_url="/docs" if settings.app_env != "prod" else None,
        redoc_url="/redoc" if settings.app_env != "prod" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(security_headers_middleware)
    app.middleware("http")(request_context_middleware)
    install_exception_handlers(app)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name, "env": settings.app_env}

    @app.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        return {
            "app": settings.app_name,
            "status": "ok",
            "docs": "/docs",
            "api": settings.api_v1_prefix,
            "frontend": "http://localhost:3000",
        }

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
