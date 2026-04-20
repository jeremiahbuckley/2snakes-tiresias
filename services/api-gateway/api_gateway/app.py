"""
FastAPI application factory.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tiresias API",
        description="Prediction market reputation and badging platform.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: restrict to known frontend origins in prod
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from auth_service.api import router as auth_router
    app.include_router(auth_router)

    from api_gateway.router import router as data_router
    app.include_router(data_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
