"""
Algolia-powered search router
High-performance, typo-tolerant search with instant results
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
from datetime import datetime, timedelta
import traceback

from database import get_mongodb
from services.algolia_service import algolia_service
from routers.search import _convert_event_to_response, _get_filter_options
from utils.date_utils import calculate_date_range

router = APIRouter(prefix="/algolia-search", tags=["algolia-search"])
logger = logging.getLogger(__name__)

@router.get("")
async def algolia_search(
    q: str = Query(..., description="Search query with instant, typo-tolerant results"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None, description="Filter by category"),
    area: Optional[str] = Query(None, description="Filter by Dubai area"),
    date_from: Optional[datetime] = Query(None, description="Events from this date"),
    date_to: Optional[datetime] = Query(None, description="Events until this date"),
    date_filter: Optional[str] = Query(None, description="Smart date filter: today, tomorrow, this_weekend, next_weekend"),
    price_max: Optional[float] = Query(None, description="Maximum price in AED"),
    price_min: Optional[float] = Query(None, description="Minimum price in AED"),
    is_free: Optional[bool] = Query(None, description="Show only free events"),
    family_friendly: Optional[bool] = Query(None, description="Show only family-friendly events"),
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Lightning-fast search powered by Algolia
    Features:
    - Instant results (< 100ms)
    - Typo tolerance
    - Intelligent ranking
    - Advanced filtering
    - Auto-suggestions
    """
    try:
        start_time = datetime.now()
        
        if not algolia_service.enabled:
            raise HTTPException(
                status_code=503, 
                detail="Algolia search service is not configured. Please set ALGOLIA_APP_ID and ALGOLIA_API_KEY environment variables."
            )
        
        # Build filters dictionary
        filters = {}
        
        # Smart date filtering
        if date_filter:
            if date_filter == 'this_weekend':
                filters['this_weekend'] = True
            elif date_filter in ['today', 'tomorrow', 'this_week', 'next_week', 'next_weekend']:
                try:
                    start_date, end_date = calculate_date_range(date_filter)
                    filters['date_from'] = start_date
                    filters['date_to'] = end_date
                except Exception as e:
                    logger.warning(f"Failed to calculate date range for {date_filter}: {e}")
        
        # Manual date filtering
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        
        # Other filters
        if category:
            filters['category'] = category
        if area:
            filters['area'] = area
        if price_max is not None:
            filters['price_max'] = price_max
        if price_min is not None:
            filters['price_min'] = price_min
        if is_free is not None:
            filters['is_free'] = is_free
        if family_friendly is not None:
            filters['family_friendly'] = family_friendly
        
        # Enhanced query preprocessing for better results
        enhanced_query = _enhance_search_query(q)
        
        # Perform Algolia search
        search_result = await algolia_service.search_events(
            query=enhanced_query,
            page=page,
            per_page=per_page,
            filters=filters
        )
        
        # Check for errors
        if 'error' in search_result:
            raise HTTPException(status_code=500, detail=f"Search failed: {search_result['error']}")
        
        # Get filter options for frontend
        filter_options = await _get_filter_options(db)
        
        # Calculate total processing time
        total_processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Return enhanced response
        return {
            "events": search_result["events"],
            "pagination": {
                "page": search_result["page"],
                "per_page": search_result["per_page"], 
                "total": search_result["total"],
                "total_pages": search_result["total_pages"],
                "has_next": search_result["page"] < search_result["total_pages"],
                "has_prev": search_result["page"] > 1
            },
            "suggestions": search_result["suggestions"],
            "filters": filter_options,
            "search_metadata": {
                "query": q,
                "enhanced_query": enhanced_query,
                "filters_applied": len([k for k, v in filters.items() if v is not None]),
                "total_processing_time_ms": total_processing_time,
                "algolia_time_ms": search_result.get("processing_time_ms", 0),
                "service": "algolia"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Algolia search error for query '{q}': {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Search service temporarily unavailable")

def _enhance_search_query(query: str) -> str:
    """
    Enhance search query for better Algolia results
    """
    # Convert common terms
    enhancements = {
        'kids': 'kids children family',
        'children': 'children kids family',
        'family': 'family kids children',
        'free': 'free budget cheap',
        'tonight': 'today evening night',
        'weekend': 'saturday sunday weekend',
        'indoor': 'indoor inside mall',
        'outdoor': 'outdoor outside beach park'
    }
    
    enhanced = query.lower()
    for term, expansion in enhancements.items():
        if term in enhanced:
            enhanced = enhanced.replace(term, expansion)
    
    return enhanced

@router.get("/status")
async def algolia_search_status():
    """
    Check Algolia search service status
    """
    return {
        "service": "algolia",
        "enabled": algolia_service.enabled,
        "app_id": algolia_service.app_id if algolia_service.enabled else None,
        "index_name": algolia_service.index_name,
        "status": "ready" if algolia_service.enabled else "not_configured",
        "features": [
            "instant_search",
            "typo_tolerance", 
            "intelligent_ranking",
            "advanced_filtering",
            "auto_suggestions",
            "highlighting"
        ],
        "expected_response_time": "< 100ms"
    }

@router.post("/index")
async def index_events_to_algolia(
    limit: int = Query(1000, description="Number of events to index"),
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Index events from MongoDB to Algolia
    This endpoint allows you to populate/update the Algolia index
    """
    try:
        if not algolia_service.enabled:
            raise HTTPException(
                status_code=503,
                detail="Algolia service not configured"
            )
        
        # Fetch events from MongoDB
        logger.info(f"Fetching {limit} events from MongoDB for indexing...")
        events_cursor = db.events.find(
            {"status": "active"},
            limit=limit
        ).sort("updated_at", -1)
        
        events = await events_cursor.to_list(length=limit)
        
        if not events:
            return {
                "message": "No events found to index",
                "indexed_count": 0
            }
        
        # Index to Algolia
        success = await algolia_service.index_events(events)
        
        if success:
            # Configure index settings
            await algolia_service.configure_index_settings()
            
            return {
                "message": f"Successfully indexed {len(events)} events to Algolia",
                "indexed_count": len(events),
                "index_name": algolia_service.index_name
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to index events to Algolia")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Indexing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

@router.get("/suggest")
async def search_suggestions(
    q: str = Query(..., description="Partial query for suggestions"),
    max_suggestions: int = Query(5, ge=1, le=10)
):
    """
    Get search suggestions based on partial query
    """
    if not algolia_service.enabled:
        return {"suggestions": []}
    
    try:
        # You can implement query suggestions using Algolia's autocomplete
        # For now, return some smart suggestions based on the query
        suggestions = []
        
        query_lower = q.lower()
        
        if 'kid' in query_lower:
            suggestions.extend([
                "kids activities dubai",
                "children events this weekend", 
                "family fun dubai",
                "kids workshops dubai"
            ])
        elif 'free' in query_lower:
            suggestions.extend([
                "free events dubai",
                "free family activities",
                "free kids events",
                "budget activities dubai"
            ])
        elif 'weekend' in query_lower:
            suggestions.extend([
                "weekend events dubai",
                "this weekend activities",
                "saturday events dubai",
                "sunday family activities"
            ])
        else:
            suggestions.extend([
                "events dubai",
                "family activities",
                "weekend events",
                "free events dubai"
            ])
        
        return {
            "suggestions": suggestions[:max_suggestions]
        }
        
    except Exception as e:
        logger.error(f"Suggestions error: {e}")
        return {"suggestions": []}

@router.get("/facets")
async def get_search_facets():
    """
    Get available facets for filtering
    """
    if not algolia_service.enabled:
        return {"facets": {}}
    
    try:
        # You can get facet counts from Algolia
        # For now, return static facets
        return {
            "facets": {
                "categories": [
                    {"value": "family_activities", "count": 0, "label": "Family Activities"},
                    {"value": "entertainment", "count": 0, "label": "Entertainment"},
                    {"value": "educational", "count": 0, "label": "Educational"},
                    {"value": "sports", "count": 0, "label": "Sports"},
                    {"value": "dining", "count": 0, "label": "Dining"},
                    {"value": "cultural", "count": 0, "label": "Cultural"},
                    {"value": "nightlife", "count": 0, "label": "Nightlife"}
                ],
                "areas": [
                    {"value": "Downtown", "count": 0, "label": "Downtown Dubai"},
                    {"value": "Marina", "count": 0, "label": "Dubai Marina"},
                    {"value": "JBR", "count": 0, "label": "Jumeirah Beach Residence"},
                    {"value": "Business Bay", "count": 0, "label": "Business Bay"},
                    {"value": "DIFC", "count": 0, "label": "DIFC"},
                    {"value": "Jumeirah", "count": 0, "label": "Jumeirah"}
                ],
                "price_tiers": [
                    {"value": "free", "count": 0, "label": "Free"},
                    {"value": "budget", "count": 0, "label": "Budget (< 100 AED)"},
                    {"value": "mid", "count": 0, "label": "Mid-range (100-300 AED)"},
                    {"value": "premium", "count": 0, "label": "Premium (> 300 AED)"}
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Facets error: {e}")
        return {"facets": {}}