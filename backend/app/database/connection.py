from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    from app.database.models import Session, Message, LegalLead, MedicalLead
    Base.metadata.create_all(bind=engine)
    print("All tables created")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
