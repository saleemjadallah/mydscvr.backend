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
        
        # Step 2: Build smart MongoDB query
        # Start with basic text search across multiple fields
        text_conditions = []
        for keyword in keywords[:3]:  # Limit to first 3 keywords
            text_conditions.append({
                "$or": [
                    {"title": {"$regex": keyword, "$options": "i"}},
                    {"description": {"$regex": keyword, "$options": "i"}},
                    {"tags": {"$regex": keyword, "$options": "i"}},
                    {"category": {"$regex": keyword, "$options": "i"}}
                ]
            })
        
        filter_query = {
            "status": "active",
            "$and": text_conditions
        } if text_conditions else {"status": "active"}
        
        # Quick date detection
        query_lower = q.lower()
        if any(word in query_lower for word in ["today", "tonight"]):
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today.replace(hour=23, minute=59, second=59)
            filter_query["start_date"] = {"$gte": today, "$lte": tomorrow}
        elif "tomorrow" in query_lower:
            tomorrow_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow_start = tomorrow_start.replace(day=tomorrow_start.day + 1)
            tomorrow_end = tomorrow_start.replace(hour=23, minute=59, second=59)
            filter_query["start_date"] = {"$gte": tomorrow_start, "$lte": tomorrow_end}
        elif any(phrase in query_lower for phrase in ["this week", "events this week"]):
            # This week detection - Monday to Sunday of current week
            now = datetime.now()
            days_since_monday = now.weekday()  # Monday = 0, Sunday = 6
            monday = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
            sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
            filter_query["start_date"] = {"$gte": monday, "$lte": sunday}
        elif "weekend" in query_lower:
            # Simple weekend detection
            now = datetime.now()
            days_until_saturday = (5 - now.weekday()) % 7
            if days_until_saturday == 0 and now.hour >= 18:
                days_until_saturday = 7
            saturday = now.replace(hour=0, minute=0, second=0, microsecond=0)
            saturday = saturday.replace(day=saturday.day + days_until_saturday)
            sunday = saturday.replace(day=saturday.day + 1, hour=23, minute=59, second=59)
            filter_query["start_date"] = {"$gte": saturday, "$lte": sunday}
        
        # Family detection
        if any(word in query_lower for word in ["family", "kids", "children"]):
            filter_query["$or"] = [
                {"familyScore": {"$gte": 60}},
                {"tags": {"$in": ["family-friendly", "kids", "children"]}}
            ]
        
        # Step 3: Fetch limited events for AI processing with optimized fields
        skip = (page - 1) * per_page
        
        # Optimize MongoDB query to reduce tokens - fetch only relevant fields
        projection = {
            "_id": 1,
            "title": 1,
            "description": 1,
            "start_date": 1,
            "end_date": 1,
            "venue.name": 1,
            "venue.area": 1,
            "category": 1,
            "tags": 1,
            "familyScore": 1,
            "price": 1,
            "pricing.base_price": 1
        }
        
        # Get 100 events max to prevent token overflow, but only send necessary fields
        events_cursor = db.events.find(filter_query, projection).sort("start_date", 1).limit(100)
        events = await events_cursor.to_list(length=100)
        
        logger.info(f"Optimized AI Search: Found {len(events)} initial events")
        
        if not events:
            # Quick fallback search without filters
            fallback_cursor = db.events.find({"status": "active"}, projection).sort("start_date", 1).limit(50)
            events = await fallback_cursor.to_list(length=50)
        
        # Step 4: Single AI call for analysis and scoring
        ai_result = await optimized_openai_service.analyze_and_score(q, events)
        
        # Step 5: Apply AI scoring to events
        scored_events = []
        event_scores = {score["id"]: score for score in ai_result.scored_events}
        
        for event in events:
            event_id = str(event.get("_id", ""))
            if event_id in event_scores:
                score_data = event_scores[event_id]
                scored_events.append({
                    "event": event,
                    "score": score_data["score"],
                    "reason": score_data["reason"]
                })
            else:
                # Include unscored events with default score
                scored_events.append({
                    "event": event,
                    "score": 40,
                    "reason": "Additional result"
                })
        
        # Sort by score
        scored_events.sort(key=lambda x: x["score"], reverse=True)
        
        # Step 6: Apply pagination
        total_scored = len(scored_events)
        paginated_scored = scored_events[skip:skip + per_page]
        
        # Step 7: Convert to response format
        event_responses = []
        for item in paginated_scored:
            event_response = await _convert_event_to_response(item["event"])
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