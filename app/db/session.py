from supabase import create_client, Client
from fastapi import Depends
from asyncpg import create_pool

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


pool = None  # Global variable to hold the database connection pool

async def init_db_pool():
    """
    Initializes the database connection pool.

    This function creates a connection pool to the PostgreSQL database
    using the connection URL from the settings. It should be called
    during the application startup.

    :return: None
    """
    url = settings.DATABASE_URL
    global pool
    pool = await create_pool(url, statement_cache_size=0)

async def get_db_connection():
    """
    Returns the database connection pool.

    This function provides access to the global connection pool. It can
    be used to acquire connections for executing queries.

    :return: The database connection pool.
    """
    return pool

async def execute_query(query: str, *args):
    """
    Executes a query using a connection from the pool.

    This function acquires a connection from the pool, executes the given
    SQL query with the provided arguments, and returns the result.

    :param query: The SQL query to execute.
    :param args: Arguments to pass to the query (e.g., parameters for placeholders).
    :return: The result of the query.
    :raises RuntimeError: If the connection pool is not initialized.
    """
    if pool is None:
        raise RuntimeError("Database pool is not initialized.")
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)
