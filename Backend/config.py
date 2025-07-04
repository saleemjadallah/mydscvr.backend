from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    class Config:
        env_file = "Backend.env"
        env_file_encoding = "utf-8"
    # MongoDB Atlas Configuration (Primary Database)
    mongodb_url: str = os.getenv("MONGODB_URL", "mongodb+srv://support:olaabdel88@dxb.tq60png.mongodb.net/?retryWrites=true&w=majority&appName=DXB&tls=true&tlsAllowInvalidCertificates=true")
    mongodb_database: str = os.getenv("MONGODB_DATABASE", "DXB")
    
    # Optional Services
    redis_url: str = "redis://localhost:6379"
    elasticsearch_url: str = "http://localhost:9200"
    
    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "CHANGE-THIS-IN-PRODUCTION")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    refresh_token_expire_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    password_reset_token_expire_hours: int = 24
    email_verification_token_expire_hours: int = 24
    
    # AWS Configuration
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "me-central-1"
    s3_bucket_name: Optional[str] = None
    cloudfront_domain: Optional[str] = None
    
    # Application Settings
    app_name: str = os.getenv("APP_NAME", "DXB Events API")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Most cost-effective model for 2025
    openai_max_tokens: int = int(os.getenv("OPENAI_MAX_TOKENS", "1000"))
    openai_temperature: float = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))
    cors_origins: List[str] = [
        "http://localhost:3000", 
        "http://localhost:3001", 
        "http://localhost:8080",
        "https://mydscvr.ai",
        "https://www.mydscvr.ai",
        "http://mydscvr.ai",
        "https://mydscvr.xyz",
        "https://www.mydscvr.xyz"
    ]
    
    # Email Configuration
    smtp_host: Optional[str] = os.getenv("SMTP_HOST")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: Optional[str] = os.getenv("SMTP_USERNAME")
    smtp_password: Optional[str] = os.getenv("SMTP_PASSWORD")
    zepto_api_key: Optional[str] = os.getenv("ZEPTO_API_KEY")
    
    # External APIs
    timeout_dubai_webhook_secret: Optional[str] = os.getenv("TIMEOUT_DUBAI_WEBHOOK_SECRET")
    timeout_webhook_secret: Optional[str] = os.getenv("TIMEOUT_WEBHOOK_SECRET")  # Alias for compatibility
    platinumlist_webhook_secret: Optional[str] = os.getenv("PLATINUMLIST_WEBHOOK_SECRET")
    webhook_api_key: str = os.getenv("WEBHOOK_API_KEY", "dev-key")
    perplexity_api_key: Optional[str] = os.getenv("PERPLEXITY_API_KEY")
    
    # Image Service Configuration
    image_storage_path: str = os.getenv("IMAGE_STORAGE_PATH", "./storage/images")
    cdn_base_url: Optional[str] = os.getenv("CDN_BASE_URL", "https://mydscvr.xyz")
    aws_s3_bucket: Optional[str] = os.getenv("AWS_S3_BUCKET")
    
    # Google OAuth Configuration
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "CHANGE-THIS-IN-PRODUCTION")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "CHANGE-THIS-IN-PRODUCTION")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "https://mydscvr.ai/auth/google/callback")
    
    class Config:
        env_file = "Backend.env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields temporarily


# Global settings instance
settings = Settings() 