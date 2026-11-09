from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite creates a local file 'lexguard.db' directly in your backend directory
SQLALCHEMY_DATABASE_URL = "sqlite:///./lexguard.db"

# connect_args={"check_same_thread": False} is required specifically for SQLite with FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency helper for FastAPI endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()