"""
AI-powered search router using OpenAI for intelligent event discovery
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
from datetime import datetime
import traceback

from database import get_mongodb
from services.openai_service import openai_service, QueryAnalysis
from routers.search import _convert_event_to_response, _get_filter_options

router = APIRouter(prefix="/api/ai-search", tags=["ai-search"])
logger = logging.getLogger(__name__)

@router.get("")
async def ai_powered_search(
    q: str = Query(..., description="Natural language search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    AI-powered search endpoint that uses OpenAI to understand queries and match events intelligently
    """
    try:
        start_time = datetime.now()
        
        # Step 1: Use OpenAI to analyze the query
        logger.info(f"AI Search: Analyzing query '{q}'")
        analysis = await openai_service.analyze_query(q)
        
        if not openai_service.enabled:
            logger.warning("OpenAI service disabled, falling back to basic search")
            # Fallback to regular search endpoint logic would go here
            return await _fallback_search(q, page, per_page, db)
        
        # Step 2: Build MongoDB query based on AI analysis
        filter_query = {"status": "active"}
        
        # Apply time-based filtering if detected
        if analysis.date_from or analysis.date_to:
            date_filter = {}
            if analysis.date_from:
                try:
                    date_from = datetime.fromisoformat(analysis.date_from)
                    date_filter["$gte"] = date_from
                except ValueError:
                    logger.warning(f"Invalid date_from format: {analysis.date_from}")
            
            if analysis.date_to:
                try:
                    date_to = datetime.fromisoformat(analysis.date_to)
                    date_filter["$lte"] = date_to
                except ValueError:
                    logger.warning(f"Invalid date_to format: {analysis.date_to}")
            
            if date_filter:
                filter_query["start_date"] = date_filter
        
        # Apply category filtering
        if analysis.categories:
            filter_query["category"] = {"$in": analysis.categories}
        
        # Apply family-friendly filtering
        if analysis.family_friendly is True:
            filter_query["$or"] = [
                {"familySuitability.isAllAges": True},
                {"tags": {"$in": ["family-friendly", "kids", "children"]}},
                {"familyScore": {"$gte": 70}}
            ]
        
        # Apply price filtering
        if analysis.price_range:
            price_filter = {}
            if "min" in analysis.price_range:
                price_filter["$gte"] = analysis.price_range["min"]
            if "max" in analysis.price_range:
                price_filter["$lte"] = analysis.price_range["max"]
            if price_filter:
                filter_query["pricing.base_price"] = price_filter
        
        # Apply location filtering
        if analysis.location_preferences:
            location_patterns = "|".join(analysis.location_preferences)
            filter_query["venue.area"] = {"$regex": f".*({location_patterns}).*", "$options": "i"}
        
        # Step 3: Fetch events from database
        skip = (page - 1) * per_page
        
        # Get optimized pool for AI ranking - reduced for performance
        max_events_for_ai = min(30, per_page * 2)  # Get 2x requested amount for faster processing
        
        # Sort by start_date to get more relevant events first
        events_cursor = db.events.find(filter_query).sort("start_date", 1).limit(max_events_for_ai)
        events = await events_cursor.to_list(length=max_events_for_ai)
        
        logger.info(f"AI Search: Found {len(events)} events matching filters")
        
        if not events:
            # No events found, return helpful response
            return {
                "events": [],
                "ai_response": await openai_service.generate_response(q, [], analysis),
                "suggestions": await openai_service.suggest_followups(q, analysis, 0),
                "query_analysis": analysis.model_dump(),
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": 0,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False
                },
                "processing_time_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                "ai_enabled": True
            }
        
        # Step 4: Use OpenAI to intelligently score and rank events
        logger.info(f"AI Search: Using OpenAI to score {len(events)} events")
        
        # If we have too many events, do a quick pre-filter to speed up AI processing
        if len(events) > 15:
            # Simple relevance filter based on text matching before AI scoring
            query_words = set(q.lower().split())
            
            def quick_score(event):
                title_words = set((event.get('title', '') or '').lower().split())
                desc_words = set((event.get('description', '') or '')[:100].lower().split())
                tags_words = set(' '.join(event.get('tags', [])).lower().split())
                
                all_words = title_words | desc_words | tags_words
                matches = len(query_words & all_words)
                return matches
            
            # Sort by quick relevance and keep top 15 for AI scoring
            events.sort(key=quick_score, reverse=True)
            events = events[:15]
            logger.info(f"AI Search: Pre-filtered to {len(events)} events for AI scoring")
        
        scored_events = await openai_service.match_events(q, events, analysis)
        
        # Step 5: Apply pagination to AI-ranked results
        total_scored = len(scored_events)
        paginated_scored = scored_events[skip:skip + per_page]
        
        # Step 6: Convert to API response format and add AI insights
        event_responses = []
        for scored_event in paginated_scored:
            # Find the original event data
            original_event = next((e for e in events if str(e.get("_id", "")) == scored_event.event_id), None)
            if original_event:
                event_response = await _convert_event_to_response(original_event)
                # Add AI-generated insights
                event_response["ai_score"] = scored_event.score
                event_response["ai_reasoning"] = scored_event.reasoning
                event_response["ai_highlights"] = scored_event.highlights
                event_responses.append(event_response)
        
        # Step 7: Generate AI response and suggestions
        ai_response = await openai_service.generate_response(q, scored_events[:10], analysis)
        suggestions = await openai_service.suggest_followups(q, analysis, len(event_responses))
        
        # Calculate pagination
        total_pages = (total_scored + per_page - 1) // per_page
        
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.info(f"AI Search completed in {processing_time}ms for query '{q}'")
        
        return {
            "events": event_responses,
            "ai_response": ai_response,
            "suggestions": suggestions,
            "query_analysis": analysis.model_dump(),
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_scored,
                "total_pages": total_pages,
                "has_next": skip + per_page < total_scored,
                "has_prev": page > 1
            },
            "processing_time_ms": processing_time,
            "ai_enabled": True,
            "filters": await _get_filter_options(db)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI search error for query '{q}': {str(e)}\n{traceback.format_exc()}")
        # Fallback to regular search on error
        logger.info("Falling back to regular search due to AI search error")
        return await _fallback_search(q, page, per_page, db)

async def _fallback_search(query: str, page: int, per_page: int, db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """
    Fallback to basic search when AI search fails
    """
    try:
        # Simple text search across title, description, tags
        filter_query = {
            "status": "active",
            "$or": [
                {"title": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
                {"tags": {"$regex": query, "$options": "i"}},
                {"category": {"$regex": query, "$options": "i"}},
                {"venue.area": {"$regex": query, "$options": "i"}}
            ]
        }
        
        skip = (page - 1) * per_page
        events_cursor = db.events.find(filter_query).skip(skip).limit(per_page)
        events = await events_cursor.to_list(length=per_page)
        
        total = await db.events.count_documents(filter_query)
        
        # Convert to response format
        event_responses = []
        for event in events:
            event_response = await _convert_event_to_response(event)
            event_responses.append(event_response)
        
        total_pages = (total + per_page - 1) // per_page
        
        return {
            "events": event_responses,
            "ai_response": f"I found {len(event_responses)} events matching '{query}' using text search. For better results, please check your OpenAI configuration.",
            "suggestions": ["Indoor activities", "Family events", "Weekend activities", "Free events"],
            "query_analysis": {"intent": "fallback_search", "confidence": 0.1},
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": skip + per_page < total,
                "has_prev": page > 1
            },
            "processing_time_ms": 0,
            "ai_enabled": False,
            "filters": await _get_filter_options(db)
        }
        
    except Exception as e:
        logger.error(f"Fallback search also failed: {e}")
        raise HTTPException(status_code=500, detail="Search service temporarily unavailable")

@router.get("/status")
async def ai_search_status():
    """
    Check AI search service status and configuration
    """
    return {
        "ai_enabled": openai_service.enabled,
        "model": openai_service.model if openai_service.enabled else None,
        "status": "ready" if openai_service.enabled else "disabled - check OpenAI API key"
    }