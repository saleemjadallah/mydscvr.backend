"""
MyDscvr's Choice Daily Event Selection API
Creates and manages the daily featured "Event of the Day" with Firecrawl prioritization
"""

import asyncio
import json
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
import logging

from database import get_mongodb
from utils.cors_middleware import add_permanent_cors_headers, get_safe_origin

router = APIRouter(prefix="/api/mydscvr-choice", tags=["mydscvr-choice"])
logger = logging.getLogger(__name__)


class MyDscvrChoiceService:
    """Service class for MyDscvr's Choice daily event selection"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.events_collection = db.events
        self.choice_collection = db.mydscvr_daily_choice
        
    async def get_firecrawl_events(self, limit: int = 100) -> List[Dict]:
        """Get events extracted via Firecrawl (highest quality)"""
        try:
            cursor = self.events_collection.find({
                "status": "active",
                "start_date": {"$gte": datetime.now()},
                "extraction_method": "firecrawl",  # Prioritize Firecrawl events
                "family_score": {"$gte": 60}  # Family-friendly events only
            }).sort("start_date", 1).limit(limit)
            
            events = []
            async for event in cursor:
                event["_id"] = str(event["_id"])
                events.append(event)
            
            logger.info(f"🔥 Found {len(events)} Firecrawl events for selection")
            return events
        except Exception as e:
            logger.error(f"Error fetching Firecrawl events: {e}")
            return []
    
    async def get_fallback_events(self, limit: int = 100) -> List[Dict]:
        """Get fallback events if not enough Firecrawl events available"""
        try:
            cursor = self.events_collection.find({
                "status": "active", 
                "start_date": {"$gte": datetime.now()},
                "family_score": {"$gte": 60}  # Family-friendly events only
            }).sort([
                ("rating", -1),  # Highest rated first
                ("start_date", 1)  # Then by date
            ]).limit(limit)
            
            events = []
            async for event in cursor:
                event["_id"] = str(event["_id"])
                events.append(event)
                
            logger.info(f"📋 Found {len(events)} fallback events for selection")
            return events
        except Exception as e:
            logger.error(f"Error fetching fallback events: {e}")
            return []
    
    def calculate_event_score(self, event: Dict) -> Dict[str, Any]:
        """Calculate comprehensive score for event selection"""
        score_breakdown = {
            "base_score": 0,
            "firecrawl_bonus": 0,
            "family_bonus": 0,
            "rating_bonus": 0,
            "venue_bonus": 0,
            "timing_bonus": 0,
            "content_bonus": 0,
            "total_score": 0
        }
        
        # Base score
        base_score = 50
        score_breakdown["base_score"] = base_score
        
        # Firecrawl extraction bonus (40 points)
        firecrawl_bonus = 40 if event.get("extraction_method") == "firecrawl" else 0
        score_breakdown["firecrawl_bonus"] = firecrawl_bonus
        
        # Family-friendly bonus (25 points)
        family_score = event.get("family_score", 0)
        family_bonus = min(25, int(family_score * 0.25)) if family_score >= 60 else 0
        score_breakdown["family_bonus"] = family_bonus
        
        # Rating bonus (20 points)
        rating = event.get("rating", 0)
        rating_bonus = min(20, int(rating * 4)) if rating > 0 else 0
        score_breakdown["rating_bonus"] = rating_bonus
        
        # Venue quality bonus (10 points)
        venue_name = event.get("venue", {}).get("name", "").lower()
        premium_venues = ["dubai mall", "mall of emirates", "downtown dubai", "burj khalifa", "dubai opera"]
        venue_bonus = 10 if any(venue in venue_name for venue in premium_venues) else 0
        score_breakdown["venue_bonus"] = venue_bonus
        
        # Weekend timing bonus (5 points)
        try:
            event_date = datetime.fromisoformat(event.get("start_date", ""))
            timing_bonus = 5 if event_date.weekday() >= 4 else 0  # Friday=4, Saturday=5, Sunday=6
        except:
            timing_bonus = 0
        score_breakdown["timing_bonus"] = timing_bonus
        
        # Rich content bonus (15 points)
        tags_count = len(event.get("tags", []))
        has_description = len(event.get("description", "")) > 100
        has_image = bool(event.get("image_url"))
        content_bonus = min(15, tags_count * 2 + (10 if has_description else 0) + (5 if has_image else 0))
        score_breakdown["content_bonus"] = content_bonus
        
        # Calculate total
        total_score = (base_score + firecrawl_bonus + family_bonus + 
                      rating_bonus + venue_bonus + timing_bonus + content_bonus)
        score_breakdown["total_score"] = total_score
        
        return score_breakdown
    
    async def select_daily_event(self) -> Optional[Dict]:
        """Select the best event for today's MyDscvr's Choice"""
        logger.info("🎯 Starting MyDscvr's Choice daily event selection...")
        
        # Get Firecrawl events first (priority)
        firecrawl_events = await self.get_firecrawl_events(50)
        
        # Get fallback events if needed
        all_events = firecrawl_events
        if len(firecrawl_events) < 10:
            fallback_events = await self.get_fallback_events(30)
            all_events.extend(fallback_events)
        
        if not all_events:
            logger.warning("⚠️ No events available for MyDscvr's Choice selection")
            return None
        
        # Score all events
        scored_events = []
        for event in all_events:
            score_data = self.calculate_event_score(event)
            scored_events.append({
                "event": event,
                "score_breakdown": score_data,
                "total_score": score_data["total_score"]
            })
        
        # Sort by score (highest first)
        scored_events.sort(key=lambda x: x["total_score"], reverse=True)
        
        # Add daily rotation among top 5 events to prevent same event showing every day
        top_events = scored_events[:5]
        day_of_year = datetime.now().timetuple().tm_yday
        rotation_index = day_of_year % len(top_events)
        selected_event_data = top_events[rotation_index]
        
        logger.info(f"🏆 Selected event: {selected_event_data['event']['title']} "
                   f"(Score: {selected_event_data['total_score']}, "
                   f"Firecrawl: {selected_event_data['event'].get('extraction_method') == 'firecrawl'})")
        
        return selected_event_data
    
    async def save_daily_choice(self, event_data: Dict) -> Dict:
        """Save today's choice to database"""
        choice_data = {
            "date": datetime.now().date(),
            "event_id": event_data["event"]["_id"],
            "event_data": event_data["event"],
            "score_breakdown": event_data["score_breakdown"],
            "total_score": event_data["total_score"],
            "is_firecrawl": event_data["event"].get("extraction_method") == "firecrawl",
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=1)
        }
        
        # Replace today's choice if it exists
        await self.choice_collection.replace_one(
            {"date": datetime.now().date()},
            choice_data,
            upsert=True
        )
        
        logger.info(f"💾 Saved MyDscvr's Choice for {datetime.now().date()}")
        return choice_data
    
    async def get_current_choice(self) -> Optional[Dict]:
        """Get today's MyDscvr's Choice"""
        try:
            choice = await self.choice_collection.find_one({
                "date": datetime.now().date()
            })
            
            if choice:
                choice["_id"] = str(choice["_id"])
                return choice
            return None
        except Exception as e:
            logger.error(f"Error fetching current choice: {e}")
            return None


@router.get("/current")
async def get_current_mydscvr_choice(
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """Get today's MyDscvr's Choice event"""
    service = MyDscvrChoiceService(db)
    
    # Check if today's choice exists
    current_choice = await service.get_current_choice()
    
    if current_choice:
        logger.info(f"✅ Returning cached MyDscvr's Choice: {current_choice['event_data']['title']}")
        return {
            "success": True,
            "data": current_choice,
            "cached": True
        }
    else:
        # No choice for today, create one
        logger.info("🔄 No current choice found, selecting new event...")
        selected_event = await service.select_daily_event()
        
        if selected_event:
            saved_choice = await service.save_daily_choice(selected_event)
            return {
                "success": True,
                "data": saved_choice,
                "cached": False
            }
        else:
            return {
                "success": False,
                "message": "No suitable events available for MyDscvr's Choice",
                "data": None
            }


@router.post("/refresh")
async def refresh_mydscvr_choice(
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """Manually refresh today's MyDscvr's Choice (for testing or forced refresh)"""
    service = MyDscvrChoiceService(db)
    
    logger.info("🔄 Manually refreshing MyDscvr's Choice...")
    selected_event = await service.select_daily_event()
    
    if selected_event:
        saved_choice = await service.save_daily_choice(selected_event)
        return {
            "success": True,
            "message": "MyDscvr's Choice refreshed successfully",
            "data": saved_choice
        }
    else:
        return {
            "success": False,
            "message": "No suitable events available for refresh"
        }


@router.get("/history")
async def get_mydscvr_choice_history(
    days: int = 7,
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """Get MyDscvr's Choice history for the last N days"""
    service = MyDscvrChoiceService(db)
    
    start_date = datetime.now().date() - timedelta(days=days)
    
    cursor = service.choice_collection.find({
        "date": {"$gte": start_date}
    }).sort("date", -1)
    
    history = []
    async for choice in cursor:
        choice["_id"] = str(choice["_id"])
        history.append(choice)
    
    return {
        "success": True,
        "data": history,
        "days": days
    }