from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, date
from enum import Enum
from bson import ObjectId


class ExclusivityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    ULTRA = "ULTRA"


class ScoringBreakdown(BaseModel):
    uniqueness: int = Field(..., ge=0, le=10)
    exclusivity: int = Field(..., ge=0, le=10)
    cultural_significance: int = Field(..., ge=0, le=10)
    photo_opportunity: int = Field(..., ge=0, le=10)
    insider_knowledge: int = Field(..., ge=0, le=10)
    value_for_money: int = Field(..., ge=0, le=10)


class HiddenGem(BaseModel):
    gem_id: str = Field(..., description="Unique gem identifier")
    event_id: str = Field(..., description="Associated event ID")
    gem_title: str = Field(..., description="Compelling gem title")
    gem_tagline: str = Field(..., description="Brief tagline")
    mystery_teaser: str = Field(..., description="Mysterious teaser text")
    revealed_description: str = Field(..., description="Full description after reveal")
    why_hidden_gem: str = Field(..., description="Why this qualifies as a hidden gem")
    exclusivity_level: ExclusivityLevel = Field(..., description="Level of exclusivity")
    gem_category: str = Field(..., description="Category of the gem")
    experience_level: str = Field(..., description="Experience level (intimate, medium, large)")
    best_for: List[str] = Field(default_factory=list, description="Who this gem is best for")
    gem_score: int = Field(..., ge=0, le=100, description="Overall gem score")
    scoring_breakdown: ScoringBreakdown = Field(..., description="Detailed scoring breakdown")
    discovery_hints: List[str] = Field(default_factory=list, description="Hints about the gem")
    insider_tips: List[str] = Field(default_factory=list, description="Insider tips")
    gem_date: datetime = Field(..., description="Date the gem was discovered")
    reveal_time: str = Field(..., description="Time when gem is revealed")
    event_details: Optional[Dict[str, Any]] = Field(None, description="Detailed event information")
    expires_at: Optional[datetime] = Field(None, description="When gem expires")
    reveal_count: int = Field(default=0, description="Number of times revealed")
    share_count: int = Field(default=0, description="Number of times shared")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Optional event data (populated dynamically)
    event: Optional[Dict[str, Any]] = Field(None, description="Full event data")

    model_config = {
        "use_enum_values": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class GemReveal(BaseModel):
    user_id: str = Field(..., description="User who revealed the gem")
    gem_id: str = Field(..., description="Gem that was revealed")
    revealed_at: datetime = Field(default_factory=datetime.utcnow)
    feedback_score: Optional[int] = Field(None, ge=1, le=5, description="User feedback score")
    feedback_comment: Optional[str] = Field(None, description="Optional feedback comment")


class UserGemStreak(BaseModel):
    user_id: str = Field(..., description="User ID")
    current_streak: int = Field(default=0, description="Current consecutive days")
    longest_streak: int = Field(default=0, description="Longest streak ever")
    total_gems_discovered: int = Field(default=0, description="Total gems discovered")
    last_discovery_date: Optional[date] = Field(None, description="Last discovery date")
    achievements: List[str] = Field(default_factory=list, description="Unlocked achievements")
    streak_started: Optional[date] = Field(None, description="When current streak started")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def update_streak(self, discovery_date: date) -> Dict[str, Any]:
        """Update streak based on discovery date"""
        result = {"streak_maintained": False, "streak_broken": False, "new_achievement": None}
        
        # Check if this is the first discovery
        if self.last_discovery_date is None:
            self.current_streak = 1
            self.longest_streak = 1
            self.total_gems_discovered = 1
            self.last_discovery_date = discovery_date
            self.streak_started = discovery_date
            result["streak_maintained"] = True
            result["new_achievement"] = "First Discovery!"
        else:
            # Check if discovery is consecutive
            days_diff = (discovery_date - self.last_discovery_date).days
            
            if days_diff == 1:
                # Consecutive day - increase streak
                self.current_streak += 1
                self.total_gems_discovered += 1
                self.last_discovery_date = discovery_date
                result["streak_maintained"] = True
                
                # Check for new longest streak
                if self.current_streak > self.longest_streak:
                    self.longest_streak = self.current_streak
                
                # Check for achievements
                if self.current_streak == 3:
                    result["new_achievement"] = "3-Day Explorer!"
                    self.achievements.append("3-Day Explorer")
                elif self.current_streak == 7:
                    result["new_achievement"] = "Weekly Wonder!"
                    self.achievements.append("Weekly Wonder")
                elif self.current_streak == 14:
                    result["new_achievement"] = "Gem Hunter!"
                    self.achievements.append("Gem Hunter")
                elif self.current_streak == 30:
                    result["new_achievement"] = "Monthly Master!"
                    self.achievements.append("Monthly Master")
                
            elif days_diff == 0:
                # Same day - just increase total
                self.total_gems_discovered += 1
                result["streak_maintained"] = True
                
            else:
                # Streak broken
                self.current_streak = 1
                self.total_gems_discovered += 1
                self.last_discovery_date = discovery_date
                self.streak_started = discovery_date
                result["streak_broken"] = True
        
        self.updated_at = datetime.utcnow()
        return result


class DailyGemAnalytics(BaseModel):
    analytics_date: date = Field(..., description="Analytics date")
    gem_id: str = Field(..., description="Gem ID")
    total_views: int = Field(default=0, description="Total views")
    total_reveals: int = Field(default=0, description="Total reveals")
    total_shares: int = Field(default=0, description="Total shares")
    reveal_rate: float = Field(default=0.0, description="Reveal rate percentage")
    average_feedback: Optional[float] = Field(None, description="Average feedback score")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Request/Response Models
class GemRevealRequest(BaseModel):
    user_id: str = Field(..., description="User ID revealing the gem")
    feedback_score: Optional[int] = Field(None, ge=1, le=5, description="Feedback score")
    feedback_comment: Optional[str] = Field(None, description="Optional feedback")


class GemRevealResponse(BaseModel):
    success: bool = Field(..., description="Whether reveal was successful")
    gem: HiddenGem = Field(..., description="The revealed gem")
    streak_info: Dict[str, Any] = Field(..., description="User streak information")
    achievement_unlocked: Optional[str] = Field(None, description="New achievement if unlocked")


class UserStreakResponse(BaseModel):
    current_streak: int = Field(..., description="Current consecutive days")
    longest_streak: int = Field(..., description="Longest streak ever")
    total_discoveries: int = Field(..., description="Total gems discovered")
    achievements: List[str] = Field(..., description="Unlocked achievements")
    next_milestone: Optional[Dict[str, Any]] = Field(None, description="Next milestone info")


class DailyGemResponse(BaseModel):
    gem: HiddenGem = Field(..., description="The hidden gem")
    user_revealed: bool = Field(default=False, description="Whether user has revealed this gem")
    user_streak: Optional[int] = Field(None, description="User's current streak")
    reveal_deadline: datetime = Field(..., description="When gem expires")