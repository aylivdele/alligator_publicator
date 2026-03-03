from datetime import datetime
import enum
import uuid

from sqlalchemy import UUID, Boolean, Column, Enum, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    admin = "admin"
    employee = "employee"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    role = Column(Enum(UserRole, name="user_role_enum"), default=UserRole.employee, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    folder_accesses = relationship("UserFolderAccess", back_populates="user", cascade="all, delete-orphan")


class UserFolderAccess(Base):
    __tablename__ = "user_folder_access"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    folder_id = Column(Integer, ForeignKey("folders.id"), primary_key=True)

    user = relationship("User", back_populates="folder_accesses")
    folder = relationship("Folder")


class AccountResultStatus(str, enum.Enum):
    success = "success"
    failed = "failed"


class TaskAccountResult(Base):
    __tablename__ = "task_account_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("publish_tasks.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("instagram_accounts.id"), nullable=True)
    status = Column(Enum(AccountResultStatus, name="account_result_status_enum"), nullable=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("PublishTask", back_populates="account_results")
    account = relationship("InstagramAccount")

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
    account_results = relationship("TaskAccountResult", back_populates="task", cascade="all, delete-orphan")