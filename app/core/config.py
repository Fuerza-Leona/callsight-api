import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "CallSight API"
    API_V1_STR: str = "/api/v1"
    
    # Database connection
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/callcenter")
    
    # CORS settings
    BACKEND_CORS_ORIGINS: list = ["*"]
    
    # TODO: Figure out why this causes an error
    # https://docs.pydantic.dev/2.10/errors/validation_errors/#extra_forbidden
    
    # class Config:
    #     env_file = ".env"

settings = Settings()
