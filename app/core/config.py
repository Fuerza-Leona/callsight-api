from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Try to load load from .env file
try:
    load_dotenv()
except Exception:
    print("Error obtaining environment variables")


class Settings(BaseSettings):
    PROJECT_NAME: str = "CallSight API"
    API_V1_STR: str = "/api/v1"

    SUPABASE_URL: str
    SUPABASE_KEY: str

    AZURE_SUBSCRIPTION_ID: str = ""
    AZURE_RESOURCE_GROUP: str = ""
    AZURE_REGION: str = ""

    AZURE_AI_KEY: str = ""
    AZURE_AI_SPEECH_ENDPOINT: str = ""
    AZURE_AI_LANGUAGE_ENDPOINT: str = ""

    AZURE_OPEN_AI_CHAT_KEY: str = ""
    AZURE_OPEN_AI_CHAT_ENDPOINT: str = ""
    AZURE_OPEN_AI_CHAT_VERSION: str = ""
    AZURE_OPEN_AI_CHAT_DEPLOYMENT: str = ""

    LANGUAGE: str = "en"
    LOCALE: str = "en-US"
    OUTPUT_FILE: bool = False
    USE_STEREO_AUDIO: bool = False
    TESTING: bool = False

    AZURE_SEARCH_ENDPOINT: str = ""
    AZURE_SEARCH_KEY: str = ""
    AZURE_SEARCH_INDEX: str = ""
    AZURE_SEARCH_SEMANTIC_CONFIG: str = ""

    GPT_MODEL: str = "gpt-4o-mini"
    MAX_TOKENS: int = 1000
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    BATCH_SIZE: int = 1000

    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    ASSEMBLYAI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    DATABASE_URL: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
