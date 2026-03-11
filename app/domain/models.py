from datetime import datetime
import enum
import uuid

from sqlalchemy import UUID, Boolean, Column, Enum, Integer, String, DateTime, ForeignKey, Text
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


# ─── M:M junction tables ──────────────────────────────────────────────────────

class FolderInstagramAccount(Base):
    """Привязка Instagram-аккаунта к папке (M:M)."""
    __tablename__ = "folder_instagram_accounts"

    folder_id = Column(Integer, ForeignKey("folders.id", ondelete="CASCADE"), primary_key=True)
    instagram_account_id = Column(Integer, ForeignKey("instagram_accounts.id", ondelete="CASCADE"), primary_key=True)


class FolderSmmboxAccount(Base):
    """Привязка SMMBox-аккаунта к папке (M:M)."""
    __tablename__ = "folder_smmbox_accounts"

    folder_id = Column(Integer, ForeignKey("folders.id", ondelete="CASCADE"), primary_key=True)
    smmbox_account_id = Column(Integer, ForeignKey("smmbox_accounts.id", ondelete="CASCADE"), primary_key=True)


class TaskSelectedInstagramAccount(Base):
    """Выбранные Instagram-аккаунты для задачи публикации."""
    __tablename__ = "task_selected_instagram_accounts"

    task_id = Column(UUID(as_uuid=True), ForeignKey("publish_tasks.id", ondelete="CASCADE"), primary_key=True)
    instagram_account_id = Column(Integer, ForeignKey("instagram_accounts.id", ondelete="CASCADE"), primary_key=True)


class TaskSelectedSmmboxAccount(Base):
    """Выбранные SMMBox-аккаунты для задачи публикации."""
    __tablename__ = "task_selected_smmbox_accounts"

    task_id = Column(UUID(as_uuid=True), ForeignKey("publish_tasks.id", ondelete="CASCADE"), primary_key=True)
    smmbox_account_id = Column(Integer, ForeignKey("smmbox_accounts.id", ondelete="CASCADE"), primary_key=True)


# ─── Core domain models ───────────────────────────────────────────────────────

class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    instagram_accounts = relationship(
        "InstagramAccount",
        secondary="folder_instagram_accounts",
        back_populates="folders",
    )
    smmbox_accounts = relationship(
        "SmmboxAccount",
        secondary="folder_smmbox_accounts",
        back_populates="folders",
    )
    tasks = relationship("PublishTask", back_populates="folder")


class InstagramAccount(Base):
    __tablename__ = "instagram_accounts"

    id = Column(Integer, primary_key=True, index=True)
    instagram_id = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # дата истечения токена
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    folders = relationship(
        "Folder",
        secondary="folder_instagram_accounts",
        back_populates="instagram_accounts",
    )


class SmmboxAccount(Base):
    __tablename__ = "smmbox_accounts"

    id = Column(Integer, primary_key=True, index=True)
    smmbox_id = Column(String, unique=True, nullable=False)
    social = Column(String, nullable=False)   # "vk", "tg", "yt", etc.
    type = Column(String, nullable=False)     # "user", "group", "page"
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    folders = relationship(
        "Folder",
        secondary="folder_smmbox_accounts",
        back_populates="smmbox_accounts",
    )


# ─── Publish tasks ────────────────────────────────────────────────────────────

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
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

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
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    selected_instagram_accounts = relationship(
        "InstagramAccount",
        secondary="task_selected_instagram_accounts",
    )
    selected_smmbox_accounts = relationship(
        "SmmboxAccount",
        secondary="task_selected_smmbox_accounts",
    )

    instagram_results = relationship(
        "TaskInstagramResult", back_populates="task", cascade="all, delete-orphan"
    )
    smmbox_results = relationship(
        "TaskSmmboxResult", back_populates="task", cascade="all, delete-orphan"
    )


# ─── Publish results ──────────────────────────────────────────────────────────

class AccountResultStatus(str, enum.Enum):
    success = "success"
    failed = "failed"


class TaskInstagramResult(Base):
    """Результат публикации в один Instagram-аккаунт."""
    __tablename__ = "task_instagram_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("publish_tasks.id"), nullable=False)
    instagram_account_id = Column(Integer, ForeignKey("instagram_accounts.id"), nullable=True)  # nullable: аккаунт мог быть удалён

    status = Column(Enum(AccountResultStatus, name="account_result_status_enum"), nullable=False)
    error = Column(Text, nullable=True)

    media_id = Column(String, nullable=True)
    permalink = Column(String, nullable=True)
    view_count = Column(Integer, nullable=True)
    views_updated_at = Column(DateTime, nullable=True)
    million_notified = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("PublishTask", back_populates="instagram_results")
    account = relationship("InstagramAccount")


class TaskSmmboxResult(Base):
    """Результат публикации в один SMMBox-аккаунт."""
    __tablename__ = "task_smmbox_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("publish_tasks.id"), nullable=False)
    smmbox_account_id = Column(Integer, ForeignKey("smmbox_accounts.id"), nullable=True)  # nullable: аккаунт мог быть удалён

    status = Column(Enum(AccountResultStatus, name="account_result_status_enum"), nullable=False)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("PublishTask", back_populates="smmbox_results")
    account = relationship("SmmboxAccount")
