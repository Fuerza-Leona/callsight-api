from supabase import create_client, Client
from fastapi import Depends

from app.core.config import settings
def get_supabase() -> Client:
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_KEY
    supabase = create_client(url, key)
    return supabase
