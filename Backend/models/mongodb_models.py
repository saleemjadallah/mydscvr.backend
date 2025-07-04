from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from bson import ObjectId


def validate_object_id(v: Union[str, ObjectId]) -> str:
    """Validate and convert ObjectId to string"""
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str):
        if ObjectId.is_valid(v):
            return v
        else:
            raise ValueError("Invalid ObjectId format")
    raise ValueError("Invalid ObjectId type")


class VenueModel(BaseModel):
    """MongoDB Venue model for flexible venue data"""
    id: Optional[str] = Field(default=None, alias="_id")
    name: str = Field(..., description="Venue name")
    address: Optional[str] = None
    area: Optional[str] = Field(None, description="Dubai area (e.g., Marina, JBR)")
    location: Optional[Dict[str, float]] = Field(None, description="GeoJSON location")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    amenities: Optional[Dict[str, Any]] = Field(default_factory=dict)
    contact_info: Optional[Dict[str, str]] = Field(default_factory=dict)
    capacity: Optional[int] = None
    venue_type: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    ratings: Optional[Dict[str, float]] = Field(default_factory=dict)
    accessibility: Optional[Dict[str, bool]] = Field(default_factory=dict)
    parking_info: Optional[Dict[str, Any]] = Field(default_factory=dict)
    public_transport: Optional[Dict[str, str]] = Field(default_factory=dict)
    website: Optional[str] = None
    social_media: Optional[Dict[str, str]] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('id', pre=True, always=True)
    def validate_id(cls, v):
        if v is None:
            return str(ObjectId())
        return validate_object_id(v)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class EventModel(BaseModel):
    """MongoDB Event model for flexible event data"""
    id: Optional[str] = Field(default=None, alias="_id")
    title: str = Field(..., description="Event title")
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=200)
    
    # Date and time
    start_date: datetime = Field(..., description="Event start date/time")
    end_date: Optional[datetime] = None
    duration_hours: Optional[float] = None
    timezone: str = Field(default="Asia/Dubai")
    
    # Location and venue
    venue_id: Optional[str] = None
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    location: Optional[Dict[str, float]] = Field(None, description="GeoJSON location")
    area: Optional[str] = Field(None, description="Dubai area")
    
    # Pricing
    price_min: Optional[float] = Field(default=0, ge=0)
    price_max: Optional[float] = Field(None, ge=0)
    currency: str = Field(default="AED")
    pricing_details: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_free: bool = Field(default=False)
    
    # Family and age information
    age_min: Optional[int] = Field(default=0, ge=0)
    age_max: Optional[int] = Field(default=99, le=150)
    is_family_friendly: bool = Field(default=True)
    family_score: Optional[int] = Field(None, ge=0, le=100)
    age_groups: List[str] = Field(default_factory=list)
    
    # Categories and tags
    category_tags: List[str] = Field(default_factory=list)
    primary_category: Optional[str] = None
    subcategories: List[str] = Field(default_factory=list)
    event_type: Optional[str] = None
    
    # Media
    image_urls: List[str] = Field(default_factory=list)
    featured_image: Optional[str] = None
    video_urls: List[str] = Field(default_factory=list)
    
    # Booking and external info
    booking_url: Optional[str] = None
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    external_id: Optional[str] = None
    
    # Lifecycle Management Fields
    source: Optional[str] = Field(None, description="Event source identifier")
    source_priority: Optional[str] = Field(None, description="Source priority: high, medium, low")
    extraction_method: Optional[str] = Field(None, description="Method used to extract event data: firecrawl, perplexity, manual, api, scraper, unknown")
    extraction_method_updated_at: Optional[datetime] = Field(None, description="When extraction_method was last updated")
    retention_days: Optional[int] = Field(None, description="Days to retain after event end")
    delete_after: Optional[datetime] = Field(None, description="Automatic deletion date")
    scraped_at: Optional[datetime] = Field(None, description="When event was scraped")
    deleted_at: Optional[datetime] = Field(None, description="When event was soft deleted")
    
    # Event details
    languages: List[str] = Field(default=["English"])
    dress_code: Optional[str] = None
    special_requirements: List[str] = Field(default_factory=list)
    included_items: List[str] = Field(default_factory=list)
    excluded_items: List[str] = Field(default_factory=list)
    
    # Ratings and reviews
    ratings: Optional[Dict[str, float]] = Field(default_factory=dict)
    review_count: int = Field(default=0)
    popularity_score: Optional[float] = None
    
    # Status and metadata
    status: str = Field(default="active")  # active, cancelled, postponed, sold_out
    is_featured: bool = Field(default=False)
    is_verified: bool = Field(default=False)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Analytics
    view_count: int = Field(default=0)
    save_count: int = Field(default=0)
    click_count: int = Field(default=0)

    @validator('id', pre=True, always=True)
    def validate_id(cls, v):
        if v is None:
            return str(ObjectId())
        return validate_object_id(v)

    @validator('venue_id', pre=True)
    def validate_venue_id(cls, v):
        if v is None:
            return v
        return validate_object_id(v)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


# Aliases for easier imports
Event = EventModel
Venue = VenueModel


class EventSearchModel(BaseModel):
    """Model for Elasticsearch event indexing"""
    id: str
    title: str
    description: Optional[str] = None
    category_tags: List[str] = []
    area: Optional[str] = None
    price_min: Optional[float] = 0
    price_max: Optional[float] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    age_min: Optional[int] = 0
    age_max: Optional[int] = 99
    is_family_friendly: bool = True
    location: Optional[Dict[str, float]] = None
    venue_name: Optional[str] = None
    family_score: Optional[int] = None
    image_urls: List[str] = []


class EventFilterModel(BaseModel):
    """Model for event filtering and search parameters"""
    category: Optional[str] = None
    location: Optional[str] = None
    area: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    price_max: Optional[float] = None
    price_min: Optional[float] = None
    age_group: Optional[str] = None  # child, teen, adult, all
    family_friendly: Optional[bool] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_km: Optional[float] = 10  # Default 10km radius
    limit: int = 20
    offset: int = 0
    sort_by: str = "start_date"  # start_date, price, family_score, distance


class EventStatsModel(BaseModel):
    """Model for event statistics and analytics"""
    total_events: int = 0
    family_friendly_events: int = 0
    free_events: int = 0
    paid_events: int = 0
    events_by_area: Dict[str, int] = {}
    events_by_category: Dict[str, int] = {}
    average_price: Optional[float] = None
    price_ranges: Dict[str, int] = {
        "free": 0,
        "low": 0,      # 0-100 AED
        "medium": 0,   # 100-500 AED
        "high": 0      # 500+ AED
    } 