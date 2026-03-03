import asyncio
import logging
import os
import uuid

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.application.services.uniqalize_reel import ReelsUniqalizerService
from app.domain.entities import Reel
from app.domain.models import AccountResultStatus, Folder, InstagramAccount, PublishTask, TaskAccountResult, TaskStage, TaskStatus
from app.domain.repositories import InstagramPublisher
from app.infrastructure.database.db import get_db

class PublishVideoTask:
  def __init__(self, uniqalizer: ReelsUniqalizerService, instagram_publisher: InstagramPublisher):
    self.uniqalizer = uniqalizer
    self.instagram_publisher = instagram_publisher
    self.logger = logging.getLogger(__name__)

  def execute(self, task: PublishTask, db: Session):

    temp_path = task.file_path
    caption = task.caption
    try:
      task.stage = TaskStage.writing
      task.status = TaskStatus.processing
      db.commit()
      
      accounts = db.query(InstagramAccount).join(Folder).where(Folder.id == task.folder_id).all()

      if not accounts or len(accounts) == 0:
        raise Exception("Выбрано 0 акканутов")

      task.stage = TaskStage.processing
      db.commit()

      urls = self.uniqalizer.execute(temp_path, len(accounts))

      print(f"Urls of videos in s3: {urls}")

      reels = [Reel(url, caption, is_trial=True if task.is_test_mode else False) for url in urls]

      task.stage = TaskStage.uploading
      db.commit()

      async def run_tasks():
        tasks = [
            asyncio.create_task(
                self.instagram_publisher.publish_reel(reel, account)
            )
            for reel, account in zip(reels, accounts)
        ]

        return await asyncio.gather(*tasks, return_exceptions=True) 
            
      results = asyncio.run(run_tasks())
      for account, result in zip(accounts, results):
          if isinstance(result, Exception):
              self.logger.exception("Publish failed for account %s", account.instagram_id, exc_info=result)
              ar = TaskAccountResult(
                  task_id=task.id,
                  account_id=account.id,
                  status=AccountResultStatus.failed,
                  error=str(result),
              )
          else:
              ar = TaskAccountResult(
                  task_id=task.id,
                  account_id=account.id,
                  status=AccountResultStatus.success,
              )
          db.add(ar)

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