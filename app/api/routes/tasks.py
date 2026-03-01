from fastapi import APIRouter, Depends, UploadFile, File, Form
import uuid
import shutil

from sqlalchemy.orm import Session

from app.application.services.uniqalize_reel import ReelsUniqalizerService
from app.domain.models import PublishTask, TaskStatus
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
      
  return router