from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import config
from app.domain.models import Base


engine = create_engine(
    config.settings.DATABASE_URL
)

Base.metadata.create_all(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()