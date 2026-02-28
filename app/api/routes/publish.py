from fastapi import APIRouter, Depends, UploadFile, File, Form
import uuid
import shutil

from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.application.services.uniqalize_reel import ReelsUniqalizerService
from app.domain.entities import Reel
from app.domain.models import Folder, InstagramAccount
from app.domain.repositories import InstagramPublisher
from app.infrastructure.database.sqlite import get_db

def create_publish_routes(uniqalizer: ReelsUniqalizerService, instagram_publisher: InstagramPublisher):
  router = APIRouter()

  @router.post("/publish")
  async def publish_reels(
      file: UploadFile = File(...),
      caption: str = Form(...),
      selected_folder_id: int = Form(...),
      db: Session = Depends(get_db)
  ):
      accounts = db.query(InstagramAccount).join(Folder).where(Folder.id == selected_folder_id).all()

      if not accounts or len(accounts) == 0:
        return JSONResponse({"error": "Выбрано 0 акканутов"}, status_code=400)
      
      temp_path = f"/tmp/{uuid.uuid4()}.mp4"

      with open(temp_path, "wb") as buffer:
          shutil.copyfileobj(file.file, buffer)

      urls = uniqalizer.execute(temp_path, len(accounts))

      print(f"Urls of videos in s3: {urls}")

      reels = [Reel(url, caption) for url in urls]

      for index in range(0, len(reels)):
        reel = reels[index]
        account = accounts[index]
        instagram_publisher.publish_reel(reel, account) 


      
  return router