import asyncio
import logging
import threading
import time
import socket
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
import requests

from app import config
from app.application.services.publish_task import PublishVideoTask
from app.application.services.uniqalize_reel import ReelsUniqalizerService
from app.domain.models import PublishTask, TaskAccountResult, TaskStatus
from app.infrastructure.database.db import SessionLocal, get_db
from app.infrastructure.instagram.graph_api_client import InstagramGraphApiClient
from app.infrastructure.storage.s3 import S3Storage
from app.infrastructure.video.ffmpeg_processor import FFmpegUniqueReelGenerator

WORKER_ID = socket.gethostname()
MILLION_VIEWS = 1_000_000


def send_million_notification(settings: config.Settings, ar: TaskAccountResult) -> None:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHANNEL_ID:
        return
    username = ar.account.username if ar.account else "unknown"
    folder_name = ar.task.folder.name if ar.task and ar.task.folder else "—"
    permalink = ar.permalink or ""
    text = (
        "🚨 РОЛИК МИЛЛИОНИК\n\n"
        f"Аккаунт: <a href=\"https://www.instagram.com/{username}/\">@{username}</a>\n"
        f"Папка: {folder_name}\n"
        f"Ссылка на видео: <a href=\"{permalink}\">Ссылка</a>"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": settings.TELEGRAM_CHANNEL_ID, "message_thread_id": settings.TELEGRAM_THREAD_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        logging.getLogger(__name__).exception("Could not send notification to tg", e)
        pass


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


def run_views_updater(graph_api: InstagramGraphApiClient, settings: config.Settings):
    logger = logging.getLogger(__name__ + ".views")
    while True:
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(hours=settings.VIEWS_MAX_AGE_HOURS)
            results = (
                db.query(TaskAccountResult)
                .join(PublishTask, PublishTask.id == TaskAccountResult.task_id)
                .filter(
                    PublishTask.created_at >= cutoff,
                    TaskAccountResult.media_id.isnot(None),
                )
                .all()
            )
            for ar in results:
                account = ar.account
                if account is None:
                    continue
                try:
                    token = str(account.access_token)
                    mid = str(ar.media_id)
                    if ar.permalink is None:
                        link = asyncio.run(graph_api.get_reel_permalink(mid, token))
                        if link:
                            ar.permalink = link
                    views = asyncio.run(graph_api.get_reel_views(mid, token))
                    if views is not None:
                        ar.view_count = views
                        ar.views_updated_at = datetime.utcnow()
                        if views >= MILLION_VIEWS and not ar.million_notified:
                            send_million_notification(settings, ar)
                            ar.million_notified = True
                except Exception:
                    logger.exception("Failed to update views for media_id=%s account=%s", ar.media_id, account.username)
            db.commit()
        except Exception as e:
            logger.exception("Views updater error: %s", e)
        finally:
            db.close()
        time.sleep(settings.VIEWS_REFRESH_MINUTES * 60)


def run_worker():
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

    logger.info("Worker started")
    settings = config.settings
    storage = S3Storage(settings.STORAGE_ENDPOINT, settings.STORAGE_ACCESS_KEY, settings.STORAGE_SECRET_KEY, settings.STORAGE_BUCKET)
    generator = FFmpegUniqueReelGenerator()
    uniqalizer = ReelsUniqalizerService(generator, storage)
    graph_api = InstagramGraphApiClient(settings.GRAPH_API_CLIENT_ID, settings.GRAPH_API_CLIENT_SECRET, settings.GRAPH_API_REDIRECT_URI)

    threading.Thread(target=run_views_updater, args=(graph_api, settings), daemon=True).start()

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
