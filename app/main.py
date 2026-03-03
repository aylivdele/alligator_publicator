import logging

from fastapi import FastAPI
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import config
from app.api.routes import accounts, auth, folders, tasks, user_auth
from app.api.routes.admin import create_admin_routes
from app.application.services.uniqalize_reel import ReelsUniqalizerService
from app.domain.models import Base, User, UserRole
from app.infrastructure.database.db import engine, get_db
from app.infrastructure.instagram.graph_api_client import InstagramGraphApiClient
from app.infrastructure.storage.s3 import S3Storage
from app.infrastructure.video.ffmpeg_processor import FFmpegUniqueReelGenerator

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _bootstrap_admin(settings: config.Settings) -> None:
    """Create default admin account if no users exist."""
    Base.metadata.create_all(bind=engine)
    db: Session = next(get_db())
    try:
        if db.query(User).count() == 0:
            admin = User(
                username=settings.ADMIN_USERNAME,
                password_hash=pwd_context.hash(settings.ADMIN_PASSWORD),
                role=UserRole.admin,
                display_name="Admin",
            )
            db.add(admin)
            db.commit()
            logging.getLogger(__name__).info(
                "Created default admin user: %s", settings.ADMIN_USERNAME
            )
    finally:
        db.close()


def create_app() -> FastAPI:

    settings = config.settings
    storage = S3Storage(settings.STORAGE_ENDPOINT, settings.STORAGE_ACCESS_KEY, settings.STORAGE_SECRET_KEY, settings.STORAGE_BUCKET)
    generator = FFmpegUniqueReelGenerator()
    uniqalizer = ReelsUniqalizerService(generator, storage)
    graph_api = InstagramGraphApiClient(settings.GRAPH_API_CLIENT_ID, settings.GRAPH_API_CLIENT_SECRET, settings.GRAPH_API_REDIRECT_URI)
    logging.basicConfig(level=logging.INFO)

    _bootstrap_admin(settings)

    app = FastAPI(title="Instagram Publisher API")

    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

    app.include_router(user_auth.router)
    app.include_router(create_admin_routes(graph_api))
    app.include_router(folders.router, prefix="/api")
    app.include_router(accounts.router, prefix="/api")
    app.include_router(tasks.create_publish_routes(uniqalizer, graph_api), prefix="/api")
    app.include_router(auth.create_auth_routes(graph_api))

    return app
