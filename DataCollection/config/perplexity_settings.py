#!/usr/bin/env python3
"""
Perplexity-based Data Collection Settings
Clean configuration for the new Perplexity-only data collection system
"""

import os
from typing import Optional, List, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', 'DataCollection.env'))

class PerplexityDataCollectionSettings(BaseSettings):
    """Configuration settings for Perplexity-based data collection"""
    
    # Perplexity API Configuration
    PERPLEXITY_API_KEY: Optional[str] = Field(default=None, env="PERPLEXITY_API_KEY")
    PERPLEXITY_BASE_URL: str = "https://api.perplexity.ai/chat/completions"
    PERPLEXITY_MODEL: str = "sonar"
    PERPLEXITY_MAX_TOKENS: int = 4000
    PERPLEXITY_TEMPERATURE: float = 0.1
    PERPLEXITY_TIMEOUT: int = 60
    
    # Rate Limiting
    PERPLEXITY_RATE_LIMIT: int = 1000  # requests per hour
    PERPLEXITY_REQUESTS_PER_MINUTE: int = 20
    REQUEST_DELAY_SECONDS: int = 2  # Delay between requests
    
    # MongoDB Configuration  
    MONGO_URI: Optional[str] = Field(default=None, env="MONGO_URI")
    MONGO_DB_NAME: str = Field(default="DXB", env="MONGO_DB_NAME")
    
    # Collection Configuration
    EVENTS_COLLECTION: str = "events"
    SESSIONS_COLLECTION: str = "extraction_sessions"
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/perplexity_collection.log"
    LOG_ROTATION: str = "10 MB"
    LOG_RETENTION: str = "7 days"
    
    # Data Collection Parameters
    DEFAULT_SEARCH_QUERIES: List[str] = [
        "Dubai family events activities kids children",
        "Dubai nightlife bars clubs parties concerts",
        "Dubai cultural events exhibitions museums art",
        "Dubai sports events fitness activities",
        "Dubai business events conferences networking",
        "Dubai dining food festivals restaurants",
        "Dubai brunch bottomless brunch weekend brunch friday brunch",
        "Dubai entertainment shows comedy theater",
        "Dubai shopping events markets fashion",
        "Dubai outdoor activities beach water sports",
        "Dubai educational workshops classes learning",
        "Dubai festivals celebrations seasonal events",
        "Dubai luxury events VIP experiences"
    ]
    
    # Event Categories Mapping
    CATEGORY_SEARCH_MAPPING: Dict[str, str] = {
        "family": "Dubai family events activities kids children",
        "nightlife": "Dubai nightlife bars clubs parties concerts",
        "cultural": "Dubai cultural events exhibitions museums art",
        "sports": "Dubai sports events fitness activities",
        "business": "Dubai business events conferences networking",
        "dining": "Dubai dining food festivals restaurants",
        "brunch": "Dubai brunch bottomless brunch weekend brunch friday brunch",
        "entertainment": "Dubai entertainment shows comedy theater",
        "educational": "Dubai educational workshops classes learning",
        "outdoor": "Dubai outdoor activities beach water sports",
        "shopping": "Dubai shopping events markets fashion"
    }
    
    # Data Quality Settings
    MIN_EVENT_TITLE_LENGTH: int = 10
    MAX_EVENT_TITLE_LENGTH: int = 200
    MIN_DESCRIPTION_LENGTH: int = 50
    MAX_DESCRIPTION_LENGTH: int = 1000
    DEFAULT_EVENT_DURATION_HOURS: int = 2
    
    # Family Score Calculation Weights
    FAMILY_SCORE_WEIGHTS: Dict[str, float] = {
        "age_inclusivity": 0.25,
        "safety_supervision": 0.20,
        "educational_value": 0.15,
        "duration_appropriateness": 0.15,
        "venue_accessibility": 0.15,
        "pricing_family_friendly": 0.10
    }
    
    # Error Handling
    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_DELAY_SECONDS: int = 5
    
    # Firecrawl MCP Configuration
    ENABLE_FIRECRAWL_SUPPLEMENT: bool = Field(default=False, env="ENABLE_FIRECRAWL_SUPPLEMENT")
    FIRECRAWL_API_KEY: Optional[str] = Field(default=None, env="FIRECRAWL_API_KEY")
    FIRECRAWL_PLATINUMLIST_LIMIT: int = Field(default=25, env="FIRECRAWL_PLATINUMLIST_LIMIT")
    FIRECRAWL_TIMEOUT_LIMIT: int = Field(default=15, env="FIRECRAWL_TIMEOUT_LIMIT")
    FIRECRAWL_WHATSON_LIMIT: int = Field(default=10, env="FIRECRAWL_WHATSON_LIMIT")
    FIRECRAWL_REQUEST_TIMEOUT: int = Field(default=60, env="FIRECRAWL_REQUEST_TIMEOUT")
    
    # Hybrid extraction weights (for future analytics)
    SOURCE_CONFIDENCE_WEIGHTS: Dict[str, float] = {
        "perplexity_search": 0.7,
        "firecrawl_platinumlist": 0.9,
        "firecrawl_timeout": 0.8,
        "firecrawl_whatson": 0.7
    }
    
    # Storage Configuration
    ENABLE_DEDUPLICATION: bool = True
    STORE_RAW_RESPONSES: bool = True
    AUTO_CLEANUP_OLD_SESSIONS: bool = True
    SESSION_RETENTION_DAYS: int = 30
    
    class Config:
        env_file = ["DataCollection.env"]
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Validate required settings
        if not self.PERPLEXITY_API_KEY:
            raise ValueError("PERPLEXITY_API_KEY is required")
        
        if not self.MONGO_URI:
            raise ValueError("MONGO_URI is required")
    
    @property
    def mongodb_config(self) -> Dict[str, Any]:
        """Get MongoDB configuration"""
        return {
            "uri": self.MONGO_URI,
            "database": self.MONGO_DB_NAME,
            "events_collection": self.EVENTS_COLLECTION,
            "sessions_collection": self.SESSIONS_COLLECTION
        }
    
    @property
    def perplexity_config(self) -> Dict[str, Any]:
        """Get Perplexity API configuration"""
        return {
            "api_key": self.PERPLEXITY_API_KEY,
            "base_url": self.PERPLEXITY_BASE_URL,
            "model": self.PERPLEXITY_MODEL,
            "max_tokens": self.PERPLEXITY_MAX_TOKENS,
            "temperature": self.PERPLEXITY_TEMPERATURE,
            "timeout": self.PERPLEXITY_TIMEOUT
        }
    
    @property
    def rate_limit_config(self) -> Dict[str, Any]:
        """Get rate limiting configuration"""
        return {
            "requests_per_hour": self.PERPLEXITY_RATE_LIMIT,
            "requests_per_minute": self.PERPLEXITY_REQUESTS_PER_MINUTE,
            "delay_between_requests": self.REQUEST_DELAY_SECONDS
        }
    
    @property
    def firecrawl_config(self) -> Dict[str, Any]:
        """Get Firecrawl MCP configuration"""
        return {
            "api_key": self.FIRECRAWL_API_KEY,
            "enabled": self.ENABLE_FIRECRAWL_SUPPLEMENT,
            "limits": {
                "platinumlist": self.FIRECRAWL_PLATINUMLIST_LIMIT,
                "timeout": self.FIRECRAWL_TIMEOUT_LIMIT,
                "whatson": self.FIRECRAWL_WHATSON_LIMIT
            },
            "request_timeout": self.FIRECRAWL_REQUEST_TIMEOUT,
            "confidence_weights": self.SOURCE_CONFIDENCE_WEIGHTS
        }

# Global settings instance
_settings: Optional[PerplexityDataCollectionSettings] = None

def get_settings() -> PerplexityDataCollectionSettings:
    """Get or create global settings instance"""
    global _settings
    if _settings is None:
        _settings = PerplexityDataCollectionSettings()
    return _settings

def reload_settings() -> PerplexityDataCollectionSettings:
    """Reload settings from environment"""
    global _settings
    _settings = PerplexityDataCollectionSettings()
    return _settings

# Convenience functions
def get_perplexity_api_key() -> str:
    """Get Perplexity API key"""
    settings = get_settings()
    if not settings.PERPLEXITY_API_KEY:
        raise ValueError("Perplexity API key not configured")
    return settings.PERPLEXITY_API_KEY

def get_mongodb_uri() -> str:
    """Get MongoDB URI"""
    settings = get_settings()
    if not settings.MONGO_URI:
        raise ValueError("MongoDB URI not configured")
    return settings.MONGO_URI

def get_search_queries_for_category(category: str) -> str:
    """Get search query for a specific category"""
    settings = get_settings()
    return settings.CATEGORY_SEARCH_MAPPING.get(category.lower(), f"Dubai {category} events")

def get_all_search_queries() -> List[str]:
    """Get all default search queries"""
    settings = get_settings()
    return settings.DEFAULT_SEARCH_QUERIES.copy()

# Export main settings class
__all__ = [
    'PerplexityDataCollectionSettings',
    'get_settings',
    'reload_settings',
    'get_perplexity_api_key',
    'get_mongodb_uri',
    'get_search_queries_for_category',
    'get_all_search_queries'
] 