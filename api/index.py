from app import db_supabase
from app.factory import create_app

app = create_app(db_supabase)

__all__ = ["app"]
