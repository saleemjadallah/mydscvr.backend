"""
Optimized AI-powered search router with single OpenAI call
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
from datetime import datetime, timedelta
import traceback

from database import get_mongodb
from services.openai_service_optimized import optimized_openai_service
from routers.search import _convert_event_to_response, _get_filter_options

router = APIRouter(prefix="/api/ai-search-v2", tags=["ai-search-v2"])
logger = logging.getLogger(__name__)

@router.get("")
async def optimized_ai_search(
    q: str = Query(..., description="Natural language search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Optimized AI search with single OpenAI call for sub-5 second response times
    """
    try:
        start_time = datetime.now()
        
        # Step 1: Quick keyword extraction for initial filtering
        keywords = q.lower().split()
        
        # Step 2: Build smart MongoDB query with meaningful keywords only
        # Filter out common stop words and extract meaningful search terms
        stop_words = {"where", "can", "i", "my", "take", "what", "is", "are", "the", "a", "an", "to", "for", "in", "on", "at", "this", "that"}
        meaningful_keywords = [word for word in keywords if word.lower() not in stop_words and len(word) > 2]
        
        # Start with basic text search across multiple fields using meaningful keywords only
        text_conditions = []
        for keyword in meaningful_keywords[:3]:  # Limit to first 3 meaningful keywords
            text_conditions.append({
                "$or": [
                    {"title": {"$regex": keyword, "$options": "i"}},
                    {"description": {"$regex": keyword, "$options": "i"}},
                    {"tags": {"$regex": keyword, "$options": "i"}},
                    {"category": {"$regex": keyword, "$options": "i"}}
                ]
            })
        
        # Base filter with proper date filtering to exclude old events
        current_time = datetime.now()
        filter_query = {
            "status": "active",
            "end_date": {"$gte": current_time}  # Only events that haven't ended yet
        }
        
        # Add text search conditions
        if text_conditions:
            filter_query["$and"] = text_conditions
        
        # Advanced temporal query detection
        query_lower = q.lower()
        now = datetime.now()
        
        # Today and tonight
        if any(word in query_lower for word in ["today", "tonight"]):
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            if "tonight" in query_lower:
                # Tonight = after 6 PM today
                today_start = now.replace(hour=18, minute=0, second=0, microsecond=0)
            filter_query["start_date"] = {"$gte": today_start, "$lte": today_end}
            
        # Tomorrow
        elif "tomorrow" in query_lower:
            tomorrow_start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            tomorrow_end = tomorrow_start.replace(hour=23, minute=59, second=59, microsecond=999999)
            filter_query["start_date"] = {"$gte": tomorrow_start, "$lte": tomorrow_end}
            
        # This morning/afternoon
        elif "this morning" in query_lower:
            morning_start = now.replace(hour=6, minute=0, second=0, microsecond=0)
            morning_end = now.replace(hour=12, minute=0, second=0, microsecond=0)
            filter_query["start_date"] = {"$gte": morning_start, "$lte": morning_end}
        elif "this afternoon" in query_lower:
            afternoon_start = now.replace(hour=12, minute=0, second=0, microsecond=0)
            afternoon_end = now.replace(hour=18, minute=0, second=0, microsecond=0)
            filter_query["start_date"] = {"$gte": afternoon_start, "$lte": afternoon_end}
            
        # This weekend (current or upcoming) - Check BEFORE "this week" to avoid substring match
        elif any(phrase in query_lower for phrase in ["this weekend", "weekend"]):
            if now.weekday() >= 5:  # If today is Saturday or Sunday
                # Current weekend
                if now.weekday() == 5:  # Saturday
                    weekend_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                else:  # Sunday
                    weekend_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
                weekend_end = weekend_start + timedelta(days=1, hours=23, minutes=59, seconds=59, microseconds=999999)
            else:
                # Upcoming weekend
                days_until_saturday = (5 - now.weekday()) % 7
                if days_until_saturday == 0:
                    days_until_saturday = 7
                weekend_start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_until_saturday)
                weekend_end = weekend_start + timedelta(days=1, hours=23, minutes=59, seconds=59, microseconds=999999)
            
            logger.info(f"Weekend detection: {weekend_start} to {weekend_end}")
            # Advanced logic: Find events that overlap with the weekend period
            # This includes: events starting during weekend, events ending during weekend, 
            # and events that span the entire weekend period
            filter_query["$or"] = [
                # Events that start during the weekend
                {"start_date": {"$gte": weekend_start, "$lte": weekend_end}},
                # Events that end during the weekend  
                {"end_date": {"$gte": weekend_start, "$lte": weekend_end}},
                # Events that span the entire weekend (start before, end after)
                {"$and": [
                    {"start_date": {"$lte": weekend_start}},
                    {"end_date": {"$gte": weekend_end}}
                ]}
            ]
            
        # This week
        elif any(phrase in query_lower for phrase in ["this week", "events this week"]):
            days_since_monday = now.weekday()  # Monday = 0, Sunday = 6
            monday = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
            sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
            
            # Advanced logic: Find events that overlap with this week period
            filter_query["$or"] = [
                {"start_date": {"$gte": monday, "$lte": sunday}},
                {"end_date": {"$gte": monday, "$lte": sunday}},
                {"$and": [
                    {"start_date": {"$lte": monday}},
                    {"end_date": {"$gte": sunday}}
                ]}
            ]
            
        # Next week
        elif any(phrase in query_lower for phrase in ["next week", "events next week"]):
            days_since_monday = now.weekday()
            next_monday = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday) + timedelta(days=7)
            next_sunday = next_monday + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
            
            # Advanced logic: Find events that overlap with next week period
            filter_query["$or"] = [
                {"start_date": {"$gte": next_monday, "$lte": next_sunday}},
                {"end_date": {"$gte": next_monday, "$lte": next_sunday}},
                {"$and": [
                    {"start_date": {"$lte": next_monday}},
                    {"end_date": {"$gte": next_sunday}}
                ]}
            ]
            
        # Next weekend
        elif "next weekend" in query_lower:
            days_until_saturday = (5 - now.weekday()) % 7
            if days_until_saturday == 0:
                days_until_saturday = 7
            next_weekend_start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_until_saturday + 7)
            next_weekend_end = next_weekend_start + timedelta(days=1, hours=23, minutes=59, seconds=59, microseconds=999999)
            
            # Advanced logic: Find events that overlap with next weekend period
            filter_query["$or"] = [
                {"start_date": {"$gte": next_weekend_start, "$lte": next_weekend_end}},
                {"end_date": {"$gte": next_weekend_start, "$lte": next_weekend_end}},
                {"$and": [
                    {"start_date": {"$lte": next_weekend_start}},
                    {"end_date": {"$gte": next_weekend_end}}
                ]}
            ]
            
        # This month
        elif any(phrase in query_lower for phrase in ["this month", "events this month"]):
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Get last day of current month
            if now.month == 12:
                month_end = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
            else:
                month_end = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
            filter_query["start_date"] = {"$gte": month_start, "$lte": month_end}
            
        # Next month
        elif any(phrase in query_lower for phrase in ["next month", "events next month"]):
            if now.month == 12:
                next_month_start = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                next_month_end = now.replace(year=now.year + 1, month=2, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
            else:
                next_month_start = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
                if now.month == 11:
                    next_month_end = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
                else:
                    next_month_end = now.replace(month=now.month + 2, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
            filter_query["start_date"] = {"$gte": next_month_start, "$lte": next_month_end}
        
        # Price detection and filtering - use $and to avoid conflicts
        price_conditions = []
        if any(word in query_lower for word in ["free", "free events"]):
            price_conditions.append({
                "$or": [
                    {"price": {"$regex": "free", "$options": "i"}},
                    {"pricing.base_price": 0},
                    {"price": "0"},
                    {"price": "Free"}
                ]
            })
        elif any(word in query_lower for word in ["cheap", "budget", "affordable"]):
            price_conditions.append({
                "$or": [
                    {"pricing.base_price": {"$lte": 50}},
                    {"price_data.min": {"$lte": 50}}
                ]
            })
        elif any(word in query_lower for word in ["expensive", "premium", "luxury"]):
            price_conditions.append({
                "$or": [
                    {"pricing.base_price": {"$gte": 200}},
                    {"price_data.min": {"$gte": 200}}
                ]
            })
        
        # Add price conditions to the main filter
        if price_conditions:
            if "$and" not in filter_query:
                filter_query["$and"] = []
            filter_query["$and"].extend(price_conditions)
            
        # Location detection (Dubai areas)
        location_matches = {
            "downtown": ["downtown", "dubai mall", "burj khalifa"],
            "marina": ["marina", "marina walk", "marina mall"],
            "jbr": ["jbr", "jumeirah beach residence", "the beach", "the walk"],
            "business bay": ["business bay"],
            "difc": ["difc", "financial centre"],
            "jumeirah": ["jumeirah", "jumeirah beach"],
            "deira": ["deira", "old dubai", "gold souk"]
        }
        
        # Location filtering - use $and to avoid conflicts
        location_conditions = []
        for area, patterns in location_matches.items():
            if any(pattern in query_lower for pattern in patterns):
                location_conditions.append({
                    "$or": [
                        {"venue.area": {"$regex": area, "$options": "i"}},
                        {"location": {"$regex": area, "$options": "i"}},
                        {"address": {"$regex": area, "$options": "i"}}
                    ]
                })
                break
        
        # Add location conditions to the main filter
        if location_conditions:
            if "$and" not in filter_query:
                filter_query["$and"] = []
            filter_query["$and"].extend(location_conditions)
                
        # Category and activity type detection
        category_matches = {
            "music": ["concerts", "music", "concert"],
            "arts": ["art", "exhibitions", "exhibition", "gallery"],
            "sports": ["sports", "fitness", "workout", "gym"],
            "dining": ["restaurant", "dining", "food", "brunch", "dinner"],
            "nightlife": ["nightlife", "bar", "club", "nightclub"],
            "cultural": ["cultural", "museum", "heritage"],
            "educational": ["workshops", "classes", "workshop", "class", "learning"]
        }
        
        # Category filtering - use $and to avoid conflicts
        category_conditions = []
        for category, patterns in category_matches.items():
            if any(pattern in query_lower for pattern in patterns):
                category_conditions.append({
                    "$or": [
                        {"category": category},
                        {"primary_category": category},
                        {"secondary_categories": category},
                        {"tags": {"$in": patterns}}
                    ]
                })
                break
        
        # Add category conditions to the main filter
        if category_conditions:
            if "$and" not in filter_query:
                filter_query["$and"] = []
            filter_query["$and"].extend(category_conditions)
                
        # Family and age detection - use $and to avoid overwriting other $or conditions
        family_conditions = []
        if any(word in query_lower for word in ["family", "family-friendly", "family events"]):
            family_conditions.append({
                "$or": [
                    {"is_family_friendly": True},
                    {"familyScore": {"$gte": 70}},
                    {"tags": {"$in": ["family-friendly", "family", "kids"]}}
                ]
            })
        elif any(word in query_lower for word in ["kids", "children", "children activities"]):
            family_conditions.append({
                "$or": [
                    {"age_min": {"$lte": 12}},
                    {"tags": {"$in": ["children", "kids", "toddler"]}}
                ]
            })
        elif any(word in query_lower for word in ["adults only", "adult only", "18+"]):
            family_conditions.append({
                "$or": [
                    {"age_min": {"$gte": 18}},
                    {"age_restrictions": {"$regex": "18\\+", "$options": "i"}}
                ]
            })
        
        # Add family conditions to the main filter
        if family_conditions:
            if "$and" not in filter_query:
                filter_query["$and"] = []
            filter_query["$and"].extend(family_conditions)
            
        # Indoor/outdoor detection
        if any(word in query_lower for word in ["outdoor", "outdoor activities"]):
            filter_query["$or"] = [
                {"venue_type": "outdoor"},
                {"indoor_outdoor": "outdoor"}
            ]
        elif any(word in query_lower for word in ["indoor", "indoor activities"]):
            filter_query["$or"] = [
                {"venue_type": "indoor"},
                {"indoor_outdoor": "indoor"}
            ]
        
        # Step 3: Fetch limited events for AI processing with optimized fields
        skip = (page - 1) * per_page
        
        # Enhanced MongoDB projection for comprehensive search support
        projection = {
            "_id": 1,
            "title": 1,
            "description": 1,
            "start_date": 1,
            "end_date": 1,
            "status": 1,
            "category": 1,
            "primary_category": 1,
            "secondary_categories": 1,
            "tags": 1,
            "location": 1,
            "address": 1,
            "venue": 1,  # Include full venue object
            "price": 1,
            "pricing": 1,  # Include full pricing object
            "price_data": 1,
            "familyScore": 1,
            "is_family_friendly": 1,
            "age_min": 1,
            "age_max": 1,
            "age_group": 1,
            "age_restrictions": 1,
            "target_audience": 1,
            "event_url": 1,
            "image_url": 1,
            "image_urls": 1,
            "venue_type": 1,
            "indoor_outdoor": 1,
            "event_type": 1,
            "source_name": 1
        }
        
        # Get 100 events max to prevent token overflow, but only send necessary fields
        logger.info(f"MongoDB query: {filter_query}")
        events_cursor = db.events.find(filter_query, projection).sort("start_date", 1).limit(100)
        events = await events_cursor.to_list(length=100)
        
        logger.info(f"Optimized AI Search: Found {len(events)} initial events")
        
        if not events:
            # Quick fallback search with proper date filtering and variety
            fallback_filter = {
                "status": "active",
                "end_date": {"$gte": current_time}
            }
            # Use random sampling to get more diverse events instead of always the same ones
            fallback_cursor = db.events.aggregate([
                {"$match": fallback_filter},
                {"$sample": {"size": 50}},  # Random sampling for variety
                {"$project": projection}
            ])
            events = await fallback_cursor.to_list(length=50)
        
        # Step 4: Single AI call for analysis and scoring
        ai_result = await optimized_openai_service.analyze_and_score(q, events)
        
        # Step 5: Apply AI scoring to events - COMMENTED OUT (always returns 40)
        # scored_events = []
        # event_scores = {score["id"]: score for score in ai_result.scored_events}
        # 
        # for event in events:
        #     event_id = str(event.get("_id", ""))
        #     if event_id in event_scores:
        #         score_data = event_scores[event_id]
        #         scored_events.append({
        #             "event": event,
        #             "score": score_data["score"],
        #             "reason": score_data["reason"]
        #         })
        #     else:
        #         # Include unscored events with default score
        #         scored_events.append({
        #             "event": event,
        #             "score": 40,
        #             "reason": "Additional result"
        #         })
        # 
        # # Sort by score
        # scored_events.sort(key=lambda x: x["score"], reverse=True)
        
        # Simplified: Just use events directly without scoring
        scored_events = [{"event": event, "score": None, "reason": None} for event in events]
        
        # Step 6: Apply pagination
        total_scored = len(scored_events)
        paginated_scored = scored_events[skip:skip + per_page]
        
        # Step 7: Convert to response format
        event_responses = []
        for item in paginated_scored:
            event_response = await _convert_event_to_response(item["event"])
            # Only add AI score fields if they exist (commented out scoring system)
            if item["score"] is not None:
                event_response["ai_score"] = item["score"]
                event_response["ai_reasoning"] = item["reason"]
            event_responses.append(event_response)
        
        # Calculate response time
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.info(f"Optimized AI Search completed in {processing_time}ms")
        
        total_pages = (total_scored + per_page - 1) // per_page
        
        return {
            "events": event_responses,
            "ai_response": ai_result.ai_response,
            "suggestions": ai_result.suggestions,
            "query_analysis": {
                "keywords": ai_result.keywords,
                "time_period": ai_result.time_period,
                "categories": ai_result.categories,
                "family_friendly": ai_result.family_friendly
            },
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_scored,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            "processing_time_ms": processing_time,
            "ai_enabled": optimized_openai_service.enabled,
            "version": "v2_optimized"
        }
        
    except Exception as e:
        logger.error(f"Optimized AI search error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Search temporarily unavailable")

@router.get("/status")
async def optimized_ai_status():
    """Check optimized AI search service status"""
    return {
        "ai_enabled": optimized_openai_service.enabled,
        "model": optimized_openai_service.model if optimized_openai_service.enabled else None,
        "status": "ready" if optimized_openai_service.enabled else "disabled",
        "version": "v2_optimized",
        "expected_response_time": "< 5 seconds"
    }