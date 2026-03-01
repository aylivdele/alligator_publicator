from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.models import Base

SQLALCHEMY_DATABASE_URL = "sqlite:////data/sqlite.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

Base.metadata.create_all(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()