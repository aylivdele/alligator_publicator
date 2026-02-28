from fastapi import FastAPI

from app import config
from app.api.routes import accounts, auth, folders, publish
from app.application.services.uniqalize_reel import ReelsUniqalizerService
from app.infrastructure.instagram.graph_api_client import InstagramGraphApiClient
from app.infrastructure.storage.s3 import S3Storage
from app.infrastructure.video.ffmpeg_processor import FFmpegUniqueReelGenerator

def create_app() -> FastAPI:

    settings = config.settings
    storage = S3Storage(settings.STORAGE_ENDPOINT, settings.STORAGE_ACCESS_KEY, settings.STORAGE_SECRET_KEY, settings.STORAGE_BUCKET)
    generator = FFmpegUniqueReelGenerator()
    uniqalizer = ReelsUniqalizerService(generator, storage)
    graph_api = InstagramGraphApiClient(settings.CLIENT_ID, settings.CLIENT_SECRET, settings.REDIRECT_URI)

    app = FastAPI(title="Instagram Publisher API")

    app.include_router(folders.router, prefix="/api")
    app.include_router(accounts.router, prefix="/api")
    app.include_router(publish.create_publish_routes(uniqalizer, graph_api), prefix="/api")
    app.include_router(auth.create_auth_routes(graph_api), prefix="/")

    return app
