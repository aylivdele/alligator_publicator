from datetime import datetime
import enum
import uuid

from sqlalchemy import UUID, Boolean, Column, Enum, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    accounts = relationship("InstagramAccount", back_populates="folder")
    tasks = relationship("PublishTask", back_populates="folder")


class InstagramAccount(Base):
    __tablename__ = "instagram_accounts"

    id = Column(Integer, primary_key=True, index=True)
    instagram_id = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    expires_in = Column(Integer, default=5184000)  # секунды
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    folder = relationship("Folder", back_populates="accounts")


class TaskStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class TaskStage(str, enum.Enum):
    writing = "writing"
    processing = "processing"
    uploading = "uploading"
    done = "done"

class PublishTask(Base):
    __tablename__ = "publish_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=False)
    file_path = Column(Text)
    caption = Column(Text)
    is_test_mode = Column(Boolean, default=False, nullable=True)

    status = Column(Enum(TaskStatus, name="task_status_enum"), default=TaskStatus.pending, nullable=False)
    stage = Column(Enum(TaskStage, name="task_stage_enum"), nullable=True)
    error = Column(Text)

    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    folder = relationship("Folder", back_populates="tasks")