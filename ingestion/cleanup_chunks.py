from db.session import SessionLocal, check_connection
from db.models import Chunk




def clean(session):
    deleted = session.query(Chunk).filter(
        Chunk.is_active.is_(False),
        ~Chunk.retrieval_logs.any(),
    ).delete(synchronize_session=False)
    session.commit()
    return deleted


def main():
    session = SessionLocal()
    check_connection()
    deleted = clean(session)
    print(f"[cleanup] {deleted} inactive, unreferenced chunks deleted")
    session.close()


if __name__ == "__main__":
    main()
