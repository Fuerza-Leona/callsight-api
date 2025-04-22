from supabase import create_client, Client
from app.core.config import settings

def get_supabase() -> Client:
    """
    Initializes and returns a Supabase client.

    :return: A Supabase client instance.
    """
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_KEY
    supabase = create_client(url, key)
    return supabase
