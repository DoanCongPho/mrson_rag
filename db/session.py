from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from sqlalchemy import text

DATABASE_URL = settings.database_url

# pre_ping: hosted Postgres (e.g. Neon) closes idle connections when it auto-suspends.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check_connection():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()