import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import subprocess
import json

# Try to load from Doppler first, fall back to .env file if doppler isn't available
try:
    # Run the doppler secrets command to get all secrets as JSON
    result = subprocess.run(
        ["doppler", "secrets", "download", "--no-file", "--format", "json"], 
        capture_output=True, 
        text=True
    )
    
    if result.returncode == 0:
        # Successfully got secrets from Doppler
        secrets = json.loads(result.stdout)
        # Add secrets to environment
        for key, value in secrets.items():
            os.environ[key] = str(value)
        print("Loaded environment variables from Doppler")
    else:
        # Fall back to .env file
        print("Failed to load from Doppler, falling back to .env file")
        load_dotenv()
except Exception as e:
    # If doppler command fails for any reason, fall back to .env
    print(f"Error using Doppler: {str(e)}")
    load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "CallSight API"
    API_V1_STR: str = "/api/v1"
    
    # Supabase connection
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    # General Azure Config
    AZURE_SUBSCRIPTION_ID: str = os.getenv("AZURE_SUBSCRIPTION_ID", "")
    AZURE_RESOURCE_GROUP: str = os.getenv("AZURE_RESOURCE_GROUP", "")
    AZURE_REGION: str = os.getenv("AZURE_REGION", "")
    
    # Azure AI Services
    AZURE_AI_KEY: str = os.getenv("AZURE_AI_KEY", "")
    AZURE_AI_SPEECH_ENDPOINT: str = os.getenv("AZURE_AI_SPEECH_ENDPOINT", "")
    AZURE_AI_LANGUAGE_ENDPOINT: str = os.getenv("AZURE_AI_LANGUAGE_ENDPOINT", "")
    
    # Azure Open AI Chat
    AZURE_OPEN_AI_CHAT_KEY: str = os.getenv("AZURE_OPEN_AI_CHAT_KEY", "")
    AZURE_OPEN_AI_CHAT_ENDPOINT: str = os.getenv("AZURE_OPEN_AI_CHAT_ENDPOINT", "")
    AZURE_OPEN_AI_CHAT_VERSION: str = os.getenv("AZURE_OPEN_AI_CHAT_VERSION", "")
    AZURE_OPEN_AI_CHAT_DEPLOYMENT: str = os.getenv("AZURE_OPEN_AI_CHAT_DEPLOYMENT", "")
    
    # Azure AI Speech Transcription Config
    LANGUAGE: str = os.getenv("LANGUAGE", "en")
    LOCALE: str = os.getenv("LOCALE", "en-US")
    OUTPUT_FILE: bool = os.getenv("OUTPUT_FILE", False) 
    USE_STEREO_AUDIO: bool = os.getenv("USE_STEREO_AUDIO", False)
    TESTING: bool = os.getenv("TESTING", False)
    
    # Azure AI Search
    AZURE_SEARCH_ENDPOINT: str = os.getenv("AZURE_SEARCH_ENDPOINT", "") 
    AZURE_SEARCH_KEY: str = os.getenv("AZURE_SEARCH_KEY", "") 
    AZURE_SEARCH_INDEX: str = os.getenv("AZURE_SEARCH_INDEX", "") 
    AZURE_SEARCH_SEMANTIC_CONFIG: str = os.getenv("AZURE_SEARCH_SEMANTIC_CONFIG", "") 
    
    # CORS settings
    BACKEND_CORS_ORIGINS: list = ["*"]

    ASSEMBLYAI_API_KEY : str = os.getenv("ASSEMBLYAI_API_KEY", "")
    OPENAI_API_KEY : str = os.getenv("OPENAI_API_KEY", "")
    
    class Config:
        env_file = ".env"

settings = Settings()
