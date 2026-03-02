from fastapi import APIRouter, Depends, UploadFile, File, Form
import uuid
import shutil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.uniqalize_reel import ReelsUniqalizerService
from app.domain.models import Folder, PublishTask, TaskStatus
from app.domain.repositories import InstagramPublisher
from app.infrastructure.database.db import get_db

def create_publish_routes(uniqalizer: ReelsUniqalizerService, instagram_publisher: InstagramPublisher):
  router = APIRouter()

  @router.post("/tasks")
  async def publish_reels(
      file: UploadFile = File(...),
      caption: str = Form(...),
      selected_folder_id: int = Form(...),
      db: Session = Depends(get_db),
  ):
      temp_path = f"/shared/{uuid.uuid4()}.mp4"

      with open(temp_path, "wb") as buffer:
          shutil.copyfileobj(file.file, buffer)
      
      task = PublishTask()
      task.folder_id = selected_folder_id
      task.status = TaskStatus.pending
      task.file_path = temp_path
      task.caption = caption

      db.add(task)
      db.commit()
      db.refresh(task)

      return {
        "task_id": str(task.id),
        "status": task.status
      }
  
  @router.get("/tasks/{task_id}")
  def get_task(task_id: uuid.UUID, db: Session = Depends(get_db)):

      task = db.get(PublishTask, task_id)

      return {
          "status": task.status,
          "stage": task.stage,
          "error": task.error
      }
  @router.get("/tasks")
  def get_task(db: Session = Depends(get_db)):

      result = db.execute(
          select(PublishTask, Folder.name)
          .join(Folder, Folder.id == PublishTask.folder_id)
          .order_by(PublishTask.created_at.desc())
          .limit(10)
          ).tuples().all()
      
      return [{
          "id": task.id,
          "folderName": folderName,
          "status": task.status,
          "stage": task.stage,
          "error": task.error,
          "created_at": task.created_at,
          "locked_by": task.locked_by,
          "is_test_mode": task.is_test_mode
      } for task, folderName in result]
      
  return router