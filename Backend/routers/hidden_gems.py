#!/usr/bin/env python3
"""
Hidden Gems Discovery API Router
Clean, efficient endpoints for the Hidden Gem feature
"""

import asyncio
import json
import httpx
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
import logging

from database import get_mongodb
from utils.cors_middleware import add_permanent_cors_headers, get_safe_origin
from models.hidden_gems import (
    HiddenGem, GemReveal, UserGemStreak, DailyGemAnalytics,
    GemRevealRequest, GemRevealResponse, UserStreakResponse, DailyGemResponse,
    ExclusivityLevel, ScoringBreakdown
)
from models.notification_models import NotificationCreate, NotificationType, NotificationPriority
from config import settings

router = APIRouter(prefix="/api/hidden-gems", tags=["hidden-gems"])
logger = logging.getLogger(__name__)


class HiddenGemService:
    """Service class for Hidden Gem business logic"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.hidden_gems
        self.reveals_collection = db.gem_reveals
        self.streaks_collection = db.user_streaks
        self.analytics_collection = db.gem_analytics
        self.notifications_collection = db.notifications
        self.users_collection = db.users
    
    async def create_hidden_gems_prompt(self, all_events: List[Dict], previous_gems: List[str]) -> Dict:
        """Create enhanced prompt for AI gem discovery"""
        
        # Get recent events (next 3 days)
        today = datetime.now()
        target_date = today + timedelta(days=1)
        end_date = today + timedelta(days=3)
        
        # Filter events for the target timeframe
        relevant_events = []
        for event in all_events:
            try:
                event_date = datetime.fromisoformat(event.get('start_date', ''))
                if target_date <= event_date <= end_date:
                    relevant_events.append(event)
            except:
                continue
        
        # Limit events for token efficiency
        events_text = "\n".join([
            f"Event ID: {event.get('_id', 'N/A')} | "
            f"Title: {event.get('title', 'N/A')} | "
            f"Venue: {event.get('venue', {}).get('name', 'N/A')} | "
            f"Area: {event.get('venue', {}).get('area', 'N/A')} | "
            f"Price: AED {event.get('pricing', {}).get('base_price', 0)} | "
            f"Category: {event.get('category', 'N/A')} | "
            f"Tags: {', '.join(event.get('tags', [])[:5])} | "
            f"Description: {event.get('description', 'N/A')[:200]}..."
            for event in relevant_events[:30]  # Limit to 30 events for efficiency
        ])
        
        previous_gems_text = ", ".join(previous_gems[-7:])  # Last 7 days
        
        system_prompt = """You are Dubai's premier Hidden Gems Discovery Specialist.
        You excel at identifying unique, lesser-known events that offer exceptional experiences.
        You understand what makes an event special, exclusive, and worth discovering in Dubai's vibrant scene."""
        
        main_prompt = f"""
TASK: Identify ONE exceptional hidden gem event from tomorrow's Dubai events.

CONTEXT: This is for an exclusive "Hidden Gem of the Day" feature that creates anticipation and discovery joy for users who want to feel "in the know" about Dubai's best experiences.

EVENTS TO ANALYZE:
{events_text}

PREVIOUS HIDDEN GEMS (avoid repetition):
{previous_gems_text}

HIDDEN GEM CRITERIA:
1. UNIQUENESS: Not mainstream - something special and different
2. EXCLUSIVITY: Limited capacity, special access, or unique venue
3. AUTHENTIC EXPERIENCE: Genuine cultural, artistic, or experiential value
4. DISCOVERY FACTOR: Something people wouldn't easily find elsewhere
5. INSTAGRAM-WORTHY: Visually interesting and memorable
6. VALUE PROPOSITION: Great experience relative to cost

AVOID:
- Large commercial events
- Chain restaurant events  
- Common shopping mall activities
- Overly touristy experiences
- Events everyone already knows about

SELECT THE BEST EVENT AND RETURN ONLY VALID JSON (no additional text or formatting):
{{
  "hidden_gem": {{
    "event_id": "actual_event_id_from_list",
    "gem_title": "Enchanting Secret Rooftop Cinema Under Dubai Stars",
    "gem_tagline": "A cinematic experience most Dubai residents have never discovered",
    "mystery_teaser": "🎭 Tonight, watch classic films under the stars at a secret location known only to film enthusiasts...",
    "revealed_description": "Experience cinema like never before at this intimate rooftop screening in old Dubai. Limited to 40 people, this hidden venue offers vintage films, traditional snacks, and breathtaking city views.",
    "why_hidden_gem": "This pop-up cinema operates only monthly in a heritage building most people pass by daily. The location is shared only 24 hours before the event.",
    "exclusivity_level": "HIGH",
    "gem_category": "Cultural Cinema",
    "experience_level": "Intimate",
    "best_for": ["couples", "film_enthusiasts", "culture_seekers"],
    "gem_score": 92,
    "scoring_breakdown": {{
      "uniqueness": 9,
      "exclusivity": 10,
      "cultural_significance": 8,
      "photo_opportunity": 9,
      "insider_knowledge": 10,
      "value_for_money": 8
    }},
    "discovery_hints": [
      "🏛️ Hidden in a heritage building",
      "🎬 Film buffs' best-kept secret", 
      "⭐ Under 50 people know about this",
      "📱 No social media advertising"
    ],
    "insider_tips": [
      "Arrive early for the best cushion spots",
      "Bring a light jacket - it gets breezy on the rooftop",
      "The traditional snacks are made by local families"
    ],
    "gem_date": "{datetime.now().isoformat()}",
    "reveal_time": "12:00 PM UAE time",
    "event_details": {{
      "title": "Secret Rooftop Cinema - Classic Film Night",
      "description": "An intimate rooftop cinema experience featuring classic films under the Dubai stars. Limited to 40 guests, this monthly event takes place in a heritage building in old Dubai with traditional snacks and stunning city views.",
      "date": "2025-06-15",
      "time": "8:00 PM - 11:00 PM",
      "location": "Heritage Building, Old Dubai (exact location shared 24h before)",
      "price": "AED 150 per person",
      "capacity": "40 people max",
      "highlights": [
        "Classic film screening under the stars",
        "Traditional Arabic snacks included",
        "Panoramic Dubai skyline views",
        "Heritage building atmosphere",
        "Limited intimate setting"
      ],
      "what_to_bring": [
        "Light jacket (gets breezy)",
        "Comfortable cushions (optional)",
        "Camera for city views"
      ],
      "booking_info": "Contact via WhatsApp 24h before event",
      "cancellation_policy": "Full refund if cancelled due to weather"
    }}
  }},
  "analysis_metadata": {{
    "total_events_analyzed": {len(relevant_events)},
    "gem_selection_confidence": "high",
    "processing_timestamp": "{datetime.now().isoformat()}"
  }}
}}

IMPORTANT:
- Use an actual event_id from the provided events list
- Choose events happening tomorrow or in the next 2 days
- Create compelling, mysterious copy that builds anticipation
- Ensure scoring breakdown adds up logically
- Focus on authentic Dubai experiences over commercial ones
- CREATE MATCHING EVENT DETAILS: The event_details section should describe the SAME experience as the gem description, creating a cohesive story
- Make the event_details feel like exclusive insider information that matches the mystery and exclusivity of the gem
- Include practical details like exact timing, pricing, capacity, what to bring, and booking process
- The event details should feel like they're revealing the "full story" behind the mysterious gem
"""
        
        return {
            "system_prompt": system_prompt,
            "main_prompt": main_prompt
        }
    
    async def discover_daily_gem_with_ai(self, all_events: List[Dict], previous_gems: List[str]) -> Dict:
        """Use AI to identify and create compelling copy for daily hidden gem"""
        
        if not hasattr(settings, 'perplexity_api_key') or not settings.perplexity_api_key:
            raise HTTPException(status_code=500, detail="Perplexity API not configured")
        
        prompts = await self.create_hidden_gems_prompt(all_events, previous_gems)
        
        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {"role": "system", "content": prompts["system_prompt"]},
                {"role": "user", "content": prompts["main_prompt"]}
            ],
            "max_tokens": 2000,
            "temperature": 0.3,
            "response_format": {"type": "text"}
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.perplexity_api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    
                    # Log the raw response for debugging
                    logger.info(f"AI Response: {content[:500]}...")
                    
                    # Try to extract JSON from the text response
                    try:
                        # Look for JSON block in the response
                        start_idx = content.find('{')
                        end_idx = content.rfind('}') + 1
                        
                        if start_idx != -1 and end_idx > start_idx:
                            json_str = content[start_idx:end_idx]
                            return json.loads(json_str)
                        else:
                            logger.error(f"No JSON found in response: {content}")
                            raise ValueError("No JSON found in AI response")
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON parsing failed: {e}")
                        logger.error(f"Content: {content}")
                        raise
                else:
                    logger.error(f"Perplexity API error: {response.status_code} - {response.text}")
                    raise HTTPException(status_code=500, detail="AI gem discovery failed")
                    
            except httpx.TimeoutException:
                logger.error("Perplexity API timeout")
                raise HTTPException(status_code=500, detail="AI gem discovery timeout")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response: {e}")
                raise HTTPException(status_code=500, detail="AI response parsing failed")
    
    async def save_hidden_gem(self, gem_data: Dict) -> HiddenGem:
        """Save discovered gem to database"""
        
        gem_info = gem_data['hidden_gem']
        
        # Create HiddenGem object
        hidden_gem = HiddenGem(
            gem_id=f"gem_{datetime.now().strftime('%Y%m%d')}_{gem_info['event_id'][:8]}",
            event_id=gem_info['event_id'],
            gem_title=gem_info['gem_title'],
            gem_tagline=gem_info['gem_tagline'],
            mystery_teaser=gem_info['mystery_teaser'],
            revealed_description=gem_info['revealed_description'],
            why_hidden_gem=gem_info['why_hidden_gem'],
            exclusivity_level=ExclusivityLevel(gem_info['exclusivity_level']),
            gem_category=gem_info['gem_category'],
            experience_level=gem_info['experience_level'],
            best_for=gem_info['best_for'],
            gem_score=gem_info['gem_score'],
            scoring_breakdown=ScoringBreakdown(**gem_info['scoring_breakdown']),
            discovery_hints=gem_info['discovery_hints'],
            insider_tips=gem_info['insider_tips'],
            gem_date=datetime.now(),
            reveal_time=gem_info['reveal_time'],
            event_details=gem_info.get('event_details'),
            expires_at=datetime.now() + timedelta(days=1)
        )
        
        # Save to database
        await self.collection.insert_one(hidden_gem.dict())
        
        # Initialize analytics
        analytics = DailyGemAnalytics(
            analytics_date=date.today(),
            gem_id=hidden_gem.gem_id
        )
        analytics_dict = analytics.dict()
        # Convert date to datetime for MongoDB serialization
        if 'analytics_date' in analytics_dict:
            analytics_dict['analytics_date'] = datetime.combine(analytics_dict['analytics_date'], datetime.min.time())
        await self.analytics_collection.insert_one(analytics_dict)
        
        return hidden_gem
    
    async def get_current_gem(self, user_id: Optional[str] = None) -> Optional[DailyGemResponse]:
        """Get today's hidden gem with full event data, fallback to yesterday's if needed"""
        
        today = date.today()
        
        # Find today's gem first
        gem_doc = await self.collection.find_one({
            "gem_date": {
                "$gte": datetime.combine(today, datetime.min.time()),
                "$lt": datetime.combine(today + timedelta(days=1), datetime.min.time())
            }
        })
        
        # If no gem for today, try yesterday's gem as fallback
        if not gem_doc:
            yesterday = today - timedelta(days=1)
            gem_doc = await self.collection.find_one({
                "gem_date": {
                    "$gte": datetime.combine(yesterday, datetime.min.time()),
                    "$lt": datetime.combine(yesterday + timedelta(days=1), datetime.min.time())
                }
            })
            
            # If still no gem found, return None
            if not gem_doc:
                return None
        
        gem = HiddenGem(**gem_doc)
        
        # Fetch the full event data and add it to the gem
        if gem.event_id:
            try:
                # Try to find event by ObjectId first
                event_doc = await self.db.events.find_one({"_id": ObjectId(gem.event_id)})
            except:
                # If ObjectId conversion fails, try as string
                event_doc = await self.db.events.find_one({"_id": gem.event_id})
            
            if event_doc:
                # Convert ObjectId to string for JSON serialization
                if "_id" in event_doc:
                    event_doc["_id"] = str(event_doc["_id"])
                # Add event data to gem object
                gem.event = event_doc
        
        # Check if user has revealed this gem
        user_revealed = False
        user_streak = None
        
        if user_id and user_id.strip():
            try:
                # First try to validate ObjectId format
                if not ObjectId.is_valid(user_id):
                    logger.warning(f"Invalid ObjectId format for user_id: {user_id}")
                else:
                    # Validate user exists
                    user_doc = await self.users_collection.find_one({"_id": ObjectId(user_id)})
                    if user_doc:
                        # User exists, fetch reveal and streak data
                        reveal = await self.reveals_collection.find_one({
                            "user_id": user_id,
                            "gem_id": gem.gem_id
                        })
                        user_revealed = reveal is not None
                        
                        # Get user streak
                        streak_doc = await self.streaks_collection.find_one({"user_id": user_id})
                        if streak_doc:
                            user_streak = streak_doc.get("current_streak", 0)
                        
                        logger.info(f"Successfully fetched user data for user_id: {user_id}")
                    else:
                        logger.warning(f"User not found in database for user_id: {user_id}")
            except Exception as e:
                logger.error(f"Error fetching user data for user_id {user_id}: {e}", exc_info=True)
                # Continue without user-specific data
                pass
        
        return DailyGemResponse(
            gem=gem,
            user_revealed=user_revealed,
            user_streak=user_streak,
            reveal_deadline=gem.expires_at or datetime.now() + timedelta(hours=12)
        )
    
    async def reveal_gem(self, gem_id: str, request: GemRevealRequest) -> GemRevealResponse:
        """Handle gem reveal by user"""
        
        # Get the gem
        gem_doc = await self.collection.find_one({"gem_id": gem_id})
        if not gem_doc:
            raise HTTPException(status_code=404, detail="Gem not found")
        
        gem = HiddenGem(**gem_doc)
        
        # Check if already revealed
        existing_reveal = await self.reveals_collection.find_one({
            "user_id": request.user_id,
            "gem_id": gem_id
        })
        
        if existing_reveal:
            # Return existing reveal
            streak_doc = await self.streaks_collection.find_one({"user_id": request.user_id})
            streak_info = {"current_streak": streak_doc.get("current_streak", 0) if streak_doc else 0}
            
            return GemRevealResponse(
                success=True,
                gem=gem,
                streak_info=streak_info
            )
        
        # Create new reveal
        reveal = GemReveal(
            user_id=request.user_id,
            gem_id=gem_id,
            feedback_score=request.feedback_score
        )
        
        await self.reveals_collection.insert_one(reveal.dict())
        
        # Update gem reveal count
        await self.collection.update_one(
            {"gem_id": gem_id},
            {"$inc": {"reveal_count": 1}}
        )
        
        # Update user streak
        streak_result = await self._update_user_streak(request.user_id)
        
        # Update analytics
        await self._update_analytics(gem_id, "reveal")
        
        return GemRevealResponse(
            success=True,
            gem=gem,
            streak_info=streak_result,
            achievement_unlocked=streak_result.get("new_achievement")
        )
    
    async def _update_user_streak(self, user_id: str) -> Dict[str, Any]:
        """Update user's discovery streak"""
        
        # Get or create user streak
        streak_doc = await self.streaks_collection.find_one({"user_id": user_id})
        
        if streak_doc:
            streak = UserGemStreak(**streak_doc)
        else:
            streak = UserGemStreak(user_id=user_id)
        
        # Update streak
        result = streak.update_streak(date.today())
        
        # Save updated streak
        await self.streaks_collection.replace_one(
            {"user_id": user_id},
            streak.dict(),
            upsert=True
        )
        
        return {
            "current_streak": streak.current_streak,
            "longest_streak": streak.longest_streak,
            "total_discoveries": streak.total_gems_discovered,
            "new_achievement": result.get("new_achievement"),
            "streak_maintained": result.get("streak_maintained"),
            "streak_broken": result.get("streak_broken")
        }
    
    async def create_gem_notification(self, user_id: str, gem: HiddenGem) -> bool:
        """Create a notification for a new hidden gem"""
        try:
            # Check if user has notification preferences that allow this
            user_doc = await self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user_doc:
                return False
            
            # Check notification preferences
            preferences = user_doc.get("preferences", {})
            notification_prefs = preferences.get("notification_preferences", {})
            
            # Only send if user allows new event notifications
            if not notification_prefs.get("new_events_in_area", True):
                return False
            
            # Create notification
            notification = NotificationCreate(
                user_id=user_id,
                type=NotificationType.NEW_EVENT,
                priority=NotificationPriority.NORMAL,
                title=f"🎪 Hidden Gem Discovered: {gem.gem_title}",
                body=gem.mystery_teaser,
                action_url=f"/hidden-gems/{gem.gem_id}",
                event_id=gem.event_id,
                data={
                    "gem_id": gem.gem_id,
                    "gem_category": gem.gem_category,
                    "exclusivity_level": gem.exclusivity_level,
                    "gem_score": gem.gem_score
                }
            )
            
            # Insert notification
            notification_dict = notification.dict()
            notification_dict["_id"] = str(ObjectId())
            await self.notifications_collection.insert_one(notification_dict)
            
            logger.info(f"Created hidden gem notification for user {user_id}: {gem.gem_title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create notification for user {user_id}: {e}")
            return False
    
    async def notify_all_users_about_gem(self, gem: HiddenGem) -> int:
        """Notify all users about a new hidden gem"""
        try:
            # Get all active users who have notification preferences enabled
            users_cursor = self.users_collection.find({
                "is_active": True,
                "is_email_verified": True,
                "$or": [
                    {"preferences.notification_preferences.new_events_in_area": True},
                    {"preferences.notification_preferences.new_events_in_area": {"$exists": False}}  # Default to true
                ]
            })
            
            users = await users_cursor.to_list(length=None)
            notification_count = 0
            
            for user in users:
                user_id = str(user["_id"])
                success = await self.create_gem_notification(user_id, gem)
                if success:
                    notification_count += 1
            
            logger.info(f"Sent hidden gem notifications to {notification_count} users")
            return notification_count
            
        except Exception as e:
            logger.error(f"Failed to notify users about gem: {e}")
            return 0
    
    async def _update_analytics(self, gem_id: str, action: str):
        """Update gem analytics"""
        
        today = date.today()
        
        update_query = {}
        if action == "view":
            update_query = {"$inc": {"total_views": 1}}
        elif action == "reveal":
            update_query = {"$inc": {"total_reveals": 1}}
        elif action == "share":
            update_query = {"$inc": {"total_shares": 1}}
        
        if update_query:
            await self.analytics_collection.update_one(
                {"gem_id": gem_id, "analytics_date": today},
                update_query,
                upsert=True
            )
    
    async def get_user_streak(self, user_id: str) -> UserStreakResponse:
        """Get user's streak information"""
        
        streak_doc = await self.streaks_collection.find_one({"user_id": user_id})
        
        if not streak_doc:
            return UserStreakResponse(
                current_streak=0,
                longest_streak=0,
                total_discoveries=0,
                achievements=[]
            )
        
        streak = UserGemStreak(**streak_doc)
        
        # Calculate next milestone
        next_milestone = None
        milestones = [3, 7, 14, 30, 50, 100]
        for milestone in milestones:
            if streak.current_streak < milestone:
                next_milestone = {
                    "target": milestone,
                    "remaining": milestone - streak.current_streak,
                    "reward": f"Achievement unlocked at {milestone} days!"
                }
                break
        
        return UserStreakResponse(
            current_streak=streak.current_streak,
            longest_streak=streak.longest_streak,
            total_discoveries=streak.total_gems_discovered,
            achievements=streak.achievements,
            next_milestone=next_milestone
        )


# API Endpoints
@router.post("/daily", response_model=HiddenGem)
async def discover_daily_gem(
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """Trigger daily gem discovery process"""
    
    service = HiddenGemService(db)
    
    # Check if today's gem already exists
    today = date.today()
    existing_gem = await service.collection.find_one({
        "gem_date": {
            "$gte": datetime.combine(today, datetime.min.time()),
            "$lt": datetime.combine(today + timedelta(days=1), datetime.min.time())
        }
    })
    
    if existing_gem:
        return HiddenGem(**existing_gem)
    
    try:
        # Get all active events
        events_cursor = db.events.find({"status": "active"})
        all_events = await events_cursor.to_list(length=None)
        
        # Get previous gems to avoid repetition
        previous_gems_cursor = service.collection.find(
            {"gem_date": {"$gte": datetime.now() - timedelta(days=7)}},
            {"gem_title": 1}
        )
        previous_gems_docs = await previous_gems_cursor.to_list(length=7)
        previous_gems = [doc.get("gem_title", "") for doc in previous_gems_docs]
        
        # Discover gem using AI
        gem_data = await service.discover_daily_gem_with_ai(all_events, previous_gems)
        
        # Save gem
        hidden_gem = await service.save_hidden_gem(gem_data)
        
        logger.info(f"✨ Daily hidden gem discovered: {hidden_gem.gem_title}")
        
        # Send notifications to users in background
        background_tasks.add_task(service.notify_all_users_about_gem, hidden_gem)
        
        return hidden_gem
        
    except Exception as e:
        logger.error(f"Failed to discover daily gem: {e}")
        raise HTTPException(status_code=500, detail="Failed to discover daily gem")


@router.get("/current")
async def get_current_gem(
    request: Request,
    response: Response,
    user_id: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """Get today's hidden gem with permanent CORS support"""
    
    # Add permanent CORS headers to ensure frontend access
    safe_origin = get_safe_origin(request)
    add_permanent_cors_headers(response, safe_origin)
    
    try:
        logger.info(f"Getting current gem for user_id: {user_id}")
        service = HiddenGemService(db)
        
        gem_response = await service.get_current_gem(user_id)
        
        if not gem_response:
            logger.warning("No gem found for today")
            # Create a proper error response with CORS headers
            from fastapi.responses import JSONResponse
            error_response = JSONResponse(
                status_code=200,
                content={
                    "success": False,
                    "message": "No gem available for today",
                    "error_code": "NO_GEM_FOUND"
                }
            )
            add_permanent_cors_headers(error_response, safe_origin)
            return error_response
        
        # Track view analytics (only if user_id is valid)
        if user_id and user_id.strip() and ObjectId.is_valid(user_id):
            try:
                await service._update_analytics(gem_response.gem.gem_id, "view")
            except Exception as e:
                logger.warning(f"Failed to update analytics: {e}")
        
        logger.info(f"Successfully returned gem: {gem_response.gem.gem_title}")
        return gem_response.dict()
        
    except Exception as e:
        logger.error(f"Error in get_current_gem: {e}", exc_info=True)
        # Create a proper error response with CORS headers
        from fastapi.responses import JSONResponse
        error_response = JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error while fetching gem",
                "error_code": "INTERNAL_ERROR",
                "details": str(e) if hasattr(settings, 'debug') and settings.debug else None
            }
        )
        add_permanent_cors_headers(error_response, safe_origin)
        return error_response


@router.post("/reveal/{gem_id}", response_model=GemRevealResponse)
async def reveal_gem(
    gem_id: str,
    request: GemRevealRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """Mark gem as revealed for user and track engagement"""
    
    service = HiddenGemService(db)
    
    return await service.reveal_gem(gem_id, request)


@router.get("/streak/{user_id}", response_model=UserStreakResponse)
async def get_user_streak(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """Get user's discovery streak and achievements"""
    
    service = HiddenGemService(db)
    
    return await service.get_user_streak(user_id)


@router.post("/share/{gem_id}")
async def share_gem(
    gem_id: str,
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """Track gem sharing"""
    
    service = HiddenGemService(db)
    
    # Update gem share count
    await service.collection.update_one(
        {"gem_id": gem_id},
        {"$inc": {"share_count": 1}}
    )
    
    # Update analytics
    await service._update_analytics(gem_id, "share")
    
    return {"success": True, "message": "Gem share tracked"}


@router.get("/gems/{gem_id}")
async def get_gem_by_id(
    gem_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """Get specific gem by ID"""
    
    service = HiddenGemService(db)
    
    gem_doc = await service.collection.find_one({"gem_id": gem_id})
    
    if not gem_doc:
        raise HTTPException(status_code=404, detail="Gem not found")
    
    return HiddenGem(**gem_doc)


@router.get("/history")
async def get_gem_history(
    limit: int = 7,
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """Get recent gem history"""
    
    service = HiddenGemService(db)
    
    # Get recent gems
    gems_cursor = service.collection.find(
        {},
        {"gem_date": 1, "gem_title": 1, "gem_tagline": 1, "gem_score": 1, "gem_id": 1}
    ).sort("gem_date", -1).limit(limit)
    
    gems = await gems_cursor.to_list(length=limit)
    
    return [HiddenGem(**gem) for gem in gems]


@router.get("/analytics/summary")
async def get_analytics_summary(
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """Get gem analytics summary"""
    
    service = HiddenGemService(db)
    
    # Get total gems count
    total_gems = await service.collection.count_documents({})
    
    # Get total reveals
    total_reveals = await service.reveals_collection.count_documents({})
    
    # Get active streaks
    active_streaks = await service.streaks_collection.count_documents({"current_streak": {"$gt": 0}})
    
    # Get average gem score
    pipeline = [
        {"$group": {"_id": None, "avg_score": {"$avg": "$gem_score"}}}
    ]
    avg_score_result = await service.collection.aggregate(pipeline).to_list(length=1)
    avg_score = avg_score_result[0]["avg_score"] if avg_score_result else 0
    
    return {
        "total_gems": total_gems,
        "total_reveals": total_reveals,
        "active_streaks": active_streaks,
        "average_gem_score": round(avg_score, 1)
    }