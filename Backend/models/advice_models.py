from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from bson import ObjectId
from enum import Enum


def validate_object_id(v) -> str:
    """Validate and convert ObjectId to string"""
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str):
        try:
            ObjectId(v)
            return v
        except Exception:
            raise ValueError("Invalid ObjectId format")
    raise ValueError("Invalid ObjectId type")


class AdviceCategory(str, Enum):
    """Categories for event advice"""
    FIRST_TIME = "first_time"
    FAMILY_TIPS = "family_tips"
    ACCESSIBILITY = "accessibility"
    TRANSPORTATION = "transportation"
    BUDGET_TIPS = "budget_tips"
    WHAT_TO_EXPECT = "what_to_expect"
    BEST_TIME = "best_time"
    GENERAL = "general"


class AdviceType(str, Enum):
    """Types of advice based on experience"""
    ATTENDED_SIMILAR = "attended_similar"
    ATTENDED_THIS = "attended_this"
    LOCAL_KNOWLEDGE = "local_knowledge"
    EXPERT_TIP = "expert_tip"


class EventAdviceModel(BaseModel):
    """MongoDB model for event advice"""
    id: Optional[str] = Field(default=None, alias="_id")
    event_id: str = Field(..., description="Event ID this advice relates to")
    user_id: str = Field(..., description="User ID who provided the advice")
    user_name: str = Field(..., description="Display name of the user")
    user_avatar: Optional[str] = Field(None, description="User avatar URL")
    
    # Advice content
    title: str = Field(..., description="Brief title for the advice", max_length=100)
    content: str = Field(..., description="Main advice content", max_length=1000)
    category: AdviceCategory = Field(..., description="Category of advice")
    advice_type: AdviceType = Field(..., description="Type of advice based on experience")
    
    # Experience details
    experience_date: Optional[datetime] = Field(None, description="When they attended the event/similar event")
    venue_familiarity: bool = Field(default=False, description="Is user familiar with the venue")
    similar_events_attended: Optional[int] = Field(None, description="Number of similar events attended")
    
    # Rating and validation
    helpfulness_rating: float = Field(default=0.0, ge=0, le=5, description="How helpful other users found this advice")
    helpfulness_votes: int = Field(default=0, description="Number of helpfulness votes")
    is_verified: bool = Field(default=False, description="Whether advice is verified by moderators")
    is_featured: bool = Field(default=False, description="Whether advice is featured")
    
    # User interaction
    helpful_users: List[str] = Field(default_factory=list, description="User IDs who found this helpful")
    reported_by: List[str] = Field(default_factory=list, description="User IDs who reported this advice")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Tags for categorizing advice")
    language: str = Field(default="en", description="Language of the advice")
    device_info: Optional[Dict[str, str]] = Field(default_factory=dict, description="Device info when advice was created")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    moderated_at: Optional[datetime] = Field(None, description="When advice was moderated")

    @validator('id', pre=True, always=True)
    def validate_id(cls, v):
        if v is None:
            return str(ObjectId())
        return validate_object_id(v)

    @validator('user_id', pre=True)
    def validate_user_id(cls, v):
        return validate_object_id(v)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class EventAdviceStatsModel(BaseModel):
    """Statistics for event advice"""
    event_id: str
    total_advice: int = Field(default=0)
    average_helpfulness: float = Field(default=0.0)
    advice_by_category: Dict[str, int] = Field(default_factory=dict)
    advice_by_type: Dict[str, int] = Field(default_factory=dict)
    verified_advice_count: int = Field(default=0)
    featured_advice_count: int = Field(default=0)
    recent_advice_count: int = Field(default=0, description="Advice in the last 30 days")
    top_tags: List[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class AdviceFilterModel(BaseModel):
    """Model for filtering event advice"""
    event_id: Optional[str] = None
    category: Optional[AdviceCategory] = None
    advice_type: Optional[AdviceType] = None
    min_helpfulness: Optional[float] = None
    verified_only: bool = False
    featured_only: bool = False
    recent_only: bool = False  # Last 30 days
    tags: Optional[List[str]] = None
    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="helpfulness_rating", description="helpfulness_rating, created_at, updated_at")
    sort_order: str = Field(default="desc", description="asc or desc")


class CreateAdviceModel(BaseModel):
    """Model for creating new advice"""
    event_id: str
    title: str = Field(..., max_length=100)
    content: str = Field(..., max_length=1000)
    category: AdviceCategory
    advice_type: AdviceType
    experience_date: Optional[datetime] = None
    venue_familiarity: bool = False
    similar_events_attended: Optional[int] = None
    tags: List[str] = Field(default_factory=list, max_items=5)
    language: str = Field(default="en")


class AdviceInteractionModel(BaseModel):
    """Model for user interactions with advice"""
    advice_id: str
    user_id: str
    interaction_type: str = Field(..., description="helpful, not_helpful, report")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    reason: Optional[str] = Field(None, description="Reason for report if applicable")


# Aliases for easier imports
EventAdvice = EventAdviceModel
AdviceStats = EventAdviceStatsModel
AdviceFilter = AdviceFilterModel
CreateAdvice = CreateAdviceModel
AdviceInteraction = AdviceInteractionModel 