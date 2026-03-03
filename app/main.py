import logging

from fastapi import FastAPI
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import config
from app.api.routes import accounts, auth, folders, tasks, user_auth, views
from app.api.routes.admin import create_admin_routes
from app.application.services.uniqalize_reel import ReelsUniqalizerService
from app.domain.models import Base, User, UserRole
from app.infrastructure.database.db import engine, get_db
from app.infrastructure.instagram.graph_api_client import InstagramGraphApiClient
from app.infrastructure.storage.s3 import S3Storage
from app.infrastructure.video.ffmpeg_processor import FFmpegUniqueReelGenerator

def create_app() -> FastAPI:

    settings = config.settings
    storage = S3Storage(settings.STORAGE_ENDPOINT, settings.STORAGE_ACCESS_KEY, settings.STORAGE_SECRET_KEY, settings.STORAGE_BUCKET)
    generator = FFmpegUniqueReelGenerator()
    uniqalizer = ReelsUniqalizerService(generator, storage)
    graph_api = InstagramGraphApiClient(settings.GRAPH_API_CLIENT_ID, settings.GRAPH_API_CLIENT_SECRET, settings.GRAPH_API_REDIRECT_URI)
    logging.basicConfig(level=logging.INFO)

    app = FastAPI(title="Instagram Publisher API")

    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

    app.include_router(user_auth.router)
    app.include_router(create_admin_routes(graph_api))
    app.include_router(folders.router, prefix="/api")
    app.include_router(accounts.router, prefix="/api")
    app.include_router(tasks.create_publish_routes(uniqalizer, graph_api), prefix="/api")
    app.include_router(views.create_views_router(settings), prefix="/api")
    app.include_router(auth.create_auth_routes(graph_api, settings))

    return app
