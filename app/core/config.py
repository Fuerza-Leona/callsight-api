import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "CallSight API"
    API_V1_STR: str = "/api/v1"
    
    # Database connection
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    # CORS settings
    BACKEND_CORS_ORIGINS: list = ["*"]
    
    # TODO: Figure out why this causes an error
    # https://docs.pydantic.dev/2.10/errors/validation_errors/#extra_forbidden
    
    # class Config:
    #     env_file = ".env"

settings = Settings()
