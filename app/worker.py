import logging
import time
import socket
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import config
from app.application.services.publish_task import PublishVideoTask
from app.application.services.uniqalize_reel import ReelsUniqalizerService
from app.domain.models import PublishTask, TaskStatus
from app.infrastructure.database.db import SessionLocal, get_db
from app.infrastructure.instagram.graph_api_client import InstagramGraphApiClient
from app.infrastructure.storage.s3 import S3Storage
from app.infrastructure.video.ffmpeg_processor import FFmpegUniqueReelGenerator

WORKER_ID = socket.gethostname()

def fetch_task(db: Session):
    task = db.execute(
        select(PublishTask)
        .where(PublishTask.status == TaskStatus.pending)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalar_one_or_none()

    if task:
        task.status = TaskStatus.processing
        task.locked_at = datetime.utcnow()
        task.locked_by = WORKER_ID
        db.commit()

    return task

def run_worker():
    logger = logging.getLogger(__name__)
    logger.info("Worker started")
    settings = config.settings
    storage = S3Storage(settings.STORAGE_ENDPOINT, settings.STORAGE_ACCESS_KEY, settings.STORAGE_SECRET_KEY, settings.STORAGE_BUCKET)
    generator = FFmpegUniqueReelGenerator()
    uniqalizer = ReelsUniqalizerService(generator, storage)
    graph_api = InstagramGraphApiClient(settings.GRAPH_API_CLIENT_ID, settings.GRAPH_API_CLIENT_SECRET, settings.GRAPH_API_REDIRECT_URI)

    while True:
        db = SessionLocal()
            
        try:
            task = fetch_task(db)

            if not task:
                time.sleep(3)
                continue

            processor = PublishVideoTask(uniqalizer, graph_api)
            processor.execute(task, db)

        except Exception as e:
            logger.exception("Worker error:", e)
        finally:
            db.close()

if __name__ == "__main__":
    run_worker()