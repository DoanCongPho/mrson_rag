from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from sqlalchemy import text

DATABASE_URL = settings.database_url

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check_connection():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))