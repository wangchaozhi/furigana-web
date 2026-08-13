from app import db_postgres
from app.factory import create_app

app = create_app(db_postgres)

__all__ = ["app"]
