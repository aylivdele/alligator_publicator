import asyncio
import json
import logging
import os
import random
import time
import uuid
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.application.services.caption_uniqualizer import CaptionUniqualizerService
from app.application.services.uniqalize_reel import ReelsUniqalizerService
from app.domain.entities import Reel
from app.domain.models import AccountResultStatus, Folder, InstagramAccount, PublishTask, TaskAccountResult, TaskStage, TaskStatus
from app.domain.repositories import InstagramPublisher
from app.infrastructure.database.db import get_db

class PublishVideoTask:
  def __init__(self, uniqalizer: ReelsUniqalizerService, instagram_publisher: InstagramPublisher, caption_uniqualizer: Optional[CaptionUniqualizerService] = None):
    self.uniqalizer = uniqalizer
    self.instagram_publisher = instagram_publisher
    self.caption_uniqualizer = caption_uniqualizer
    self.logger = logging.getLogger(__name__)

  def execute(self, task: PublishTask, db: Session):

    temp_path = task.file_path
    caption = task.caption
    try:
      task.stage = TaskStage.writing
      task.status = TaskStatus.processing
      db.commit()
      
      if task.selected_account_ids:
        ids = json.loads(task.selected_account_ids)
        accounts = db.query(InstagramAccount).filter(InstagramAccount.id.in_(ids)).all()
      else:
        accounts = db.query(InstagramAccount).join(Folder).where(Folder.id == task.folder_id).all()

      if not accounts or len(accounts) == 0:
        raise Exception("Выбрано 0 акканутов")

      task.stage = TaskStage.processing
      db.commit()

      urls = self.uniqalizer.execute(temp_path, len(accounts))

      self.logger.info("Urls of videos in s3: %s", urls)

      is_trial = bool(task.is_test_mode)
      reels = []
      for url in urls:
          unique_caption = caption
          if self.caption_uniqualizer and caption:
              try:
                  unique_caption = self.caption_uniqualizer.uniqualize(caption)
              except Exception:
                  self.logger.exception("Caption uniqualization failed, using original")
          reels.append(Reel(url, unique_caption, is_trial=is_trial))

      task.stage = TaskStage.uploading
      db.commit()

      for i, (reel, account) in enumerate(zip(reels, accounts)):
          try:
              media_id = asyncio.run(self.instagram_publisher.publish_reel(reel, account))
              ar = TaskAccountResult(
                  task_id=task.id,
                  account_id=account.id,
                  status=AccountResultStatus.success,
                  media_id=media_id,
              )
          except Exception as e:
              self.logger.exception("Publish failed for account %s", account.instagram_id, exc_info=e)
              ar = TaskAccountResult(
                  task_id=task.id,
                  account_id=account.id,
                  status=AccountResultStatus.failed,
                  error=str(e),
              )
          db.add(ar)
          db.commit()

          if i < len(accounts) - 1:
              delay = random.randint(60, 120)
              self.logger.info("Sleeping %ds before next account", delay)
              time.sleep(delay)

      task.status = TaskStatus.completed
      task.stage = TaskStage.done
      db.commit()
    except Exception as e:
      if task:
        task.status = TaskStatus.failed
        task.error = str(e)
        db.commit()
      self.logger.exception("Publish video task exception", e)
    finally:
      db.close()
      if (os.path.exists(temp_path)):
        os.remove(temp_path)