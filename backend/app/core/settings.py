# backend/app/core/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    project_name: str = "Multilingual WP RAG"
    
    # Infrastructure Connections
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    redis_url: str = "redis://localhost:6379/0"
    
    # Database
    wp_db_uri: str = "mysql+pymysql://user:password@localhost:3306/wordpress"
    
    # External APIs
    groq_api_key: SecretStr
    
    # RAG Configuration
    chunk_size: int = 500
    chunk_overlap: int = 50
    embedding_model_name: str = "BAAI/bge-m3"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()