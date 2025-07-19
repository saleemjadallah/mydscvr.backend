"""
Search router for DXB Events API
Phase 2: Advanced search and discovery implementation
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from elasticsearch import AsyncElasticsearch
import re
import logging
from datetime import datetime
import traceback

from database import get_mongodb, get_elasticsearch
from schemas import (
    SearchQuery, SearchFilters, EventListResponse, SearchSuggestionsResponse, 
    SearchSuggestion, SearchFiltersResponse
)
from typing import Set
from utils.rate_limiting import search_rate_limit
# Import conversion functions
# from routers.events import _convert_event_to_response, _get_filter_options

router = APIRouter(prefix="/api/search", tags=["search"])
logger = logging.getLogger(__name__)


# Helper function to convert MongoDB event to API response
async def _convert_event_to_response(event: dict) -> dict:
    """Convert MongoDB event document to API response format"""
    from datetime import datetime
    
    # Helper to convert datetime to ISO string
    def format_date(date_val):
        if isinstance(date_val, datetime):
            return date_val.isoformat()
        return date_val
    
    # Extract image URLs with priority order
    image_urls = []
    
    # Priority order: images.ai_generated > ai_image_url > image_url > image_urls > imageUrls
    if event.get("images") and isinstance(event["images"], dict) and event["images"].get("ai_generated"):
        image_urls = [event["images"]["ai_generated"]]
    elif event.get("ai_image_url"):
        image_urls = [event["ai_image_url"]]
    elif event.get("image_url"):
        image_urls = [event["image_url"]]
    elif event.get("image_urls"):
        image_urls = event["image_urls"]
    elif event.get("imageUrls"):
        image_urls = event["imageUrls"]
    
    return {
        "id": str(event.get("_id", "")),
        "title": event.get("title", ""),
        "description": event.get("description"),
        "category": event.get("category"),
        "start_date": format_date(event.get("start_date")),
        "end_date": format_date(event.get("end_date")),
        "venue": event.get("venue", {}),
        "price": {
            "base_price": event.get("pricing", {}).get("base_price", 0),
            "currency": event.get("pricing", {}).get("currency", "AED"),
            "is_free": event.get("pricing", {}).get("base_price", 0) == 0
        },
        "family_score": event.get("familyScore"),
        "age_range": event.get("ageRange", "All ages"),
        "tags": event.get("tags", []),
        "image_urls": image_urls,
        "booking_url": event.get("bookingUrl"),
        "is_family_friendly": event.get("familySuitability", {}).get("isAllAges", False),
        "is_saved": False,
        "duration_hours": event.get("durationHours"),
        "source_name": event.get("source_name", "mydscvr")
    }


async def _get_filter_options(db) -> dict:
    """Get available filter options from database"""
    categories = await db.events.distinct("category", {"status": "active"})
    areas = await db.events.distinct("venue.area", {"status": "active"})
    
    return {
        "categories": [c for c in categories if c],
        "areas": [a for a in areas if a],
        "price_ranges": [
            {"min": 0, "max": 0, "label": "Free"},
            {"min": 1, "max": 100, "label": "Under 100 AED"},
            {"min": 101, "max": 300, "label": "101-300 AED"},
            {"min": 301, "max": 500, "label": "301-500 AED"},
            {"min": 501, "max": None, "label": "Above 500 AED"}
        ],
        "age_groups": ["All ages", "0-3 years", "4-7 years", "8-12 years", "13+ years", "Adults only"]
    }


@router.get("/")
async def search_events(
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    area: Optional[str] = Query(None, description="Dubai area"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    price_max: Optional[float] = Query(None, description="Maximum price"),
    price_min: Optional[float] = Query(None, description="Minimum price"),
    age_group: Optional[str] = Query(None, description="Age group"),
    family_friendly: Optional[bool] = Query(None, description="Family friendly only"),
    latitude: Optional[float] = Query(None, description="Latitude"),
    longitude: Optional[float] = Query(None, description="Longitude"),
    radius_km: Optional[float] = Query(10, description="Search radius"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort_by: str = Query("relevance", description="Sort by: relevance, start_date, price, family_score"),
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
    # rate_limit: bool = Depends(search_rate_limit)  # Temporarily disabled
):
    """
    Advanced search with full-text search capabilities
    """
    try:
        # If no search query, return empty results
        if not q:
            return {
                "events": [],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": 0,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False
                },
                "filters": await _get_filter_options(db)
            }
        
        # Use MongoDB search (Elasticsearch disabled for now)
        return await _mongodb_search(
            db, q, category, area, date_from, date_to, price_max, price_min,
            age_group, family_friendly, latitude, longitude, radius_km,
            page, per_page, sort_by
        )
    except Exception as e:
        logger.error(f"Search error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Search failed. Please try again.")


@router.get("/suggestions", response_model=SearchSuggestionsResponse)
async def get_search_suggestions(
    q: str = Query(..., min_length=2, description="Partial search query"),
    limit: int = Query(10, ge=1, le=20),
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
    # rate_limit: bool = Depends(search_rate_limit)  # Temporarily disabled
):
    """
    Enhanced search suggestions with comprehensive tag support
    """
    suggestions = []
    query_lower = q.lower().strip()
    
    # Priority 1: Search for exact tag matches (highest priority)
    tag_regex = {"$regex": f".*{re.escape(query_lower)}.*", "$options": "i"}
    tag_pipeline = [
        {"$match": {"status": "active", "tags": tag_regex}},
        {"$unwind": "$tags"},
        {"$match": {"tags": tag_regex}},
        {"$group": {
            "_id": "$tags",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 4}
    ]
    
    tag_results = await db.events.aggregate(tag_pipeline).to_list(length=4)
    for tag_result in tag_results:
        tag = tag_result["_id"]
        if tag and query_lower in tag.lower():
            suggestions.append(SearchSuggestion(
                text=tag.replace('-', ' ').title(),
                type="tag",
                count=tag_result["count"]
            ))
    
    # Priority 2: Search for matching event titles
    title_regex = {"$regex": f".*{re.escape(q)}.*", "$options": "i"}
    events = await db.events.find(
        {"title": title_regex, "status": "active"},
        {"title": 1}
    ).limit(3).to_list(length=3)
    
    for event in events:
        suggestions.append(SearchSuggestion(
            text=event["title"],
            type="event",
            count=1
        ))
    
    # Priority 3: Search for matching categories with enhanced names
    category_map = {
        "food_and_dining": "Food & Dining",
        "indoor_activities": "Indoor Activities", 
        "kids_and_family": "Kids & Family",
        "outdoor_activities": "Outdoor Activities",
        "water_sports": "Water Sports",
        "cultural": "Cultural Events",
        "music_and_concerts": "Music & Concerts",
        "comedy_and_shows": "Comedy & Shows",
        "sports_and_fitness": "Sports & Fitness",
        "business_and_networking": "Business & Networking",
        "tours_and_sightseeing": "Tours & Sightseeing",
        "festivals_and_celebrations": "Festivals & Celebrations"
    }
    
    categories = await db.events.distinct("category", {
        "category": {"$regex": f".*{re.escape(query_lower)}.*", "$options": "i"},
        "status": "active"
    })
    
    for category in categories[:2]:
        if category and query_lower in category.lower():
            count = await db.events.count_documents({
                "category": category,
                "status": "active"
            })
            display_name = category_map.get(category, category.replace('_', ' ').title())
            suggestions.append(SearchSuggestion(
                text=display_name,
                type="category",
                count=count
            ))
    
    # Priority 4: Search for matching areas
    areas = await db.events.distinct("venue.area", {
        "venue.area": title_regex,
        "status": "active"
    })
    
    for area in areas[:2]:
        if area and query_lower in area.lower():
            count = await db.events.count_documents({
                "venue.area": area,
                "status": "active"
            })
            suggestions.append(SearchSuggestion(
                text=area,
                type="area",
                count=count
            ))
    
    # Priority 5: Search for matching venue names
    venues = await db.events.distinct("venue.name", {
        "venue.name": title_regex,
        "status": "active"
    })
    
    for venue in venues[:2]:
        if venue and query_lower in venue.lower():
            suggestions.append(SearchSuggestion(
                text=venue,
                type="venue",
                count=1
            ))
    
    # Priority 6: Smart suggestions based on popular search patterns
    smart_suggestions = {
        "free": "Free Events",
        "weekend": "Weekend Events", 
        "family": "Family Events",
        "indoor": "Indoor Activities",
        "outdoor": "Outdoor Activities",
        "food": "Food & Dining",
        "brunch": "Brunch Events",
        "kids": "Kids Activities",
        "cultural": "Cultural Events",
        "adventure": "Adventure Activities",
        "luxury": "Luxury Experiences",
        "budget": "Budget-Friendly Events",
        "educational": "Educational Activities",
        "entertainment": "Entertainment"
    }
    
    for key, display_name in smart_suggestions.items():
        if query_lower in key and len(suggestions) < limit:
            # Count events that match this pattern
            count = await db.events.count_documents({
                "$or": [
                    {"tags": {"$regex": f".*{key}.*", "$options": "i"}},
                    {"category": {"$regex": f".*{key}.*", "$options": "i"}}
                ],
                "status": "active"
            })
            if count > 0:
                suggestions.append(SearchSuggestion(
                    text=display_name,
                    type="smart",
                    count=count
                ))
    
    # Remove duplicates and limit results
    seen_texts = set()
    unique_suggestions = []
    for suggestion in suggestions:
        if suggestion.text.lower() not in seen_texts:
            seen_texts.add(suggestion.text.lower())
            unique_suggestions.append(suggestion)
            if len(unique_suggestions) >= limit:
                break
    
    return SearchSuggestionsResponse(suggestions=unique_suggestions)


@router.get("/filters", response_model=SearchFiltersResponse)
async def get_search_filters(
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Get all available search filter options
    """
    filter_options = await _get_filter_options(db)
    
    return SearchFiltersResponse(
        categories=filter_options["categories"],
        areas=filter_options["areas"],
        price_ranges=filter_options["price_ranges"],
        age_groups=filter_options["age_groups"]
    )


@router.get("/test-aggregation")
async def test_aggregation_search(
    q: Optional[str] = Query(None, description="Test query string"),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Test aggregation pipeline for debugging
    """
    try:
        # Build simple aggregation pipeline
        pipeline = []
        
        # Match stage
        match_stage = {"status": "active"}
        if q:
            query_lower = q.lower().strip()
            match_stage["$or"] = [
                {"title": {"$regex": f".*{re.escape(query_lower)}.*", "$options": "i"}},
                {"tags": {"$regex": f".*{re.escape(query_lower)}.*", "$options": "i"}}
            ]
        
        pipeline.append({"$match": match_stage})
        
        # Add a simple sort
        pipeline.append({"$sort": {"start_date": 1}})
        
        # Limit results
        pipeline.append({"$limit": 5})
        
        # Project only needed fields
        pipeline.append({"$project": {
            "_id": 1,
            "title": 1,
            "category": 1,
            "tags": {"$slice": ["$tags", 3]},
            "start_date": 1
        }})
        
        logger.info(f"Test aggregation pipeline: {pipeline}")
        
        # Execute aggregation
        events = await db.events.aggregate(pipeline).to_list(5)
        
        # Get count using a separate aggregation
        count_pipeline = [match_stage, {"$count": "total"}]
        count_result = await db.events.aggregate([{"$match": match_stage}, {"$count": "total"}]).to_list(1)
        count = count_result[0]["total"] if count_result else 0
        
        return {
            "success": True,
            "query": q,
            "pipeline": pipeline,
            "count": count,
            "events": [
                {
                    "id": str(event.get("_id")),
                    "title": event.get("title"),
                    "category": event.get("category"),
                    "tags": event.get("tags", []),
                    "start_date": event.get("start_date").isoformat() if event.get("start_date") else None
                }
                for event in events
            ]
        }
    except Exception as e:
        logger.error(f"Test aggregation error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "query": q
        }


@router.get("/tags", response_model=dict)
async def get_popular_tags(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Get the most popular tags across all events
    """
    pipeline = [
        {"$match": {"status": "active"}},
        {"$unwind": "$tags"},
        {"$group": {
            "_id": "$tags",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit}
    ]
    
    results = await db.events.aggregate(pipeline).to_list(length=limit)
    
    # Group tags by category for better organization
    tag_categories = {
        "activities": [],
        "amenities": [],
        "audience": [],
        "venue_type": [],
        "experience": [],
        "other": []
    }
    
    activity_tags = ["outdoor", "indoor", "water", "adventure", "cultural", "educational", "entertainment"]
    amenity_tags = ["free", "parking", "food", "air-conditioned", "stroller-ok"]
    audience_tags = ["family-friendly", "kids", "adults-only", "all-ages", "toddler"]
    venue_tags = ["mall", "hotel", "beach", "rooftop", "museum", "gallery"]
    experience_tags = ["luxury", "budget-friendly", "romantic", "relaxing", "hands-on", "interactive"]
    
    for result in results:
        tag = result["_id"]
        count = result["count"]
        tag_info = {"tag": tag, "count": count}
        
        if any(t in tag.lower() for t in activity_tags):
            tag_categories["activities"].append(tag_info)
        elif any(t in tag.lower() for t in amenity_tags):
            tag_categories["amenities"].append(tag_info)
        elif any(t in tag.lower() for t in audience_tags):
            tag_categories["audience"].append(tag_info)
        elif any(t in tag.lower() for t in venue_tags):
            tag_categories["venue_type"].append(tag_info)
        elif any(t in tag.lower() for t in experience_tags):
            tag_categories["experience"].append(tag_info)
        else:
            tag_categories["other"].append(tag_info)
    
    return tag_categories


@router.get("/smart-search")
async def smart_search(
    intent: Optional[str] = Query(None, description="Search intent: find_free_events, weekend_family_fun, indoor_activities, etc."),
    q: Optional[str] = Query(None, description="Search query for flexible smart search"),
    area: Optional[str] = Query(None, description="Dubai area"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
    # rate_limit: bool = Depends(search_rate_limit)  # Temporarily disabled
):
    """
    Smart search that understands user intent and leverages tags for better results
    """
    try:
        # Define intent-to-tag mappings
        intent_mappings = {
            "find_free_events": {
                "tags": ["free", "free-event", "complimentary"],
                "price_max": 0,
                "description": "Free events and activities"
            },
            "events_today": {
                "tags": ["today", "daily-event", "happening-now"],
                "date_filter": "today",
                "description": "Events happening today in Dubai"
            },
            "weekend_activities": {
                "tags": ["weekend", "weekend-event", "family-friendly", "saturday", "sunday"],
                "date_filter": "weekend",
                "description": "Weekend activities and events"
            },
            "weekend_family_fun": {
                "tags": ["family-friendly", "weekend-event", "kids", "family"],
                "family_friendly": True,
                "description": "Perfect weekend activities for families"
            },
            "indoor_activities": {
                "tags": ["indoor", "air-conditioned", "mall-event", "museum", "gallery"],
                "category": "indoor_activities",
                "description": "Indoor activities and entertainment"
            },
            "outdoor_adventures": {
                "tags": ["outdoor", "adventure", "nature", "beach-event", "park"],
                "category": "outdoor_activities",
                "description": "Outdoor adventures and activities"
            },
            "food_experiences": {
                "tags": ["food", "dining", "restaurant", "brunch-event", "culinary"],
                "category": "food_and_dining",
                "description": "Food and dining experiences"
            },
            "brunch_events": {
                "tags": ["brunch", "brunch-event", "bottomless brunch", "weekend brunch", "friday brunch"],
                "category": "food_and_dining",
                "description": "Brunch events and bottomless brunch experiences"
            },
            "luxury_experiences": {
                "tags": ["luxury", "premium-event", "exclusive", "five-star", "vip"],
                "description": "Luxury and premium experiences"
            },
            "budget_friendly": {
                "tags": ["budget-friendly", "affordable", "cheap", "free"],
                "price_max": 100,
                "description": "Budget-friendly events and activities"
            },
            "cultural_immersion": {
                "tags": ["cultural", "heritage", "traditional", "arabic", "emirati"],
                "category": "cultural",
                "description": "Cultural and heritage experiences"
            },
            "kids_activities": {
                "tags": ["kids", "children", "educational", "family-friendly", "playground"],
                "category": "kids_and_family",
                "description": "Activities designed for children"
            },
            "romantic_dates": {
                "tags": ["romantic", "couples", "sunset", "fine-dining", "rooftop-event"],
                "description": "Perfect for romantic dates and couples"
            }
        }
        
        # If no intent provided but q is provided, analyze query for intent
        if not intent and q:
            query_lower = q.lower()
            
            # Auto-detect intent from query - Enhanced detection
            if "today" in query_lower or "happening today" in query_lower:
                intent = "events_today"
            elif "tomorrow" in query_lower or "happening tomorrow" in query_lower:
                intent = "events_today"  # Use same intent, backend will handle date
            elif ("weekend" in query_lower and ("this" in query_lower or "activities" in query_lower or "happening" in query_lower or "events" in query_lower)) or "this weekend" in query_lower or "next weekend" in query_lower:
                intent = "weekend_activities"
            elif ("week" in query_lower and ("this" in query_lower or "next" in query_lower)) or "this week" in query_lower or "next week" in query_lower:
                intent = "weekend_activities"  # Reuse weekend logic for week queries
            elif ("month" in query_lower and ("this" in query_lower or "next" in query_lower)) or "this month" in query_lower or "next month" in query_lower:
                intent = "weekend_activities"  # Reuse for broader time ranges
            elif "upcoming" in query_lower or "coming up" in query_lower or "happening soon" in query_lower or "next few days" in query_lower:
                intent = "weekend_activities"  # Reuse for general upcoming events
            elif any(day in query_lower for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
                intent = "weekend_activities"  # Handle specific day queries
            elif "free" in query_lower:
                intent = "find_free_events"
            elif "indoor" in query_lower:
                intent = "indoor_activities"
            elif "outdoor" in query_lower:
                intent = "outdoor_adventures"
            elif "brunch" in query_lower:
                intent = "brunch_events"
            elif ("kids" in query_lower or "family" in query_lower) and "weekend" in query_lower:
                intent = "weekend_family_fun"
            elif "kids" in query_lower or "children" in query_lower:
                intent = "kids_activities"
            elif "budget" in query_lower or "cheap" in query_lower or "affordable" in query_lower:
                intent = "budget_friendly"
            elif "cultural" in query_lower or "heritage" in query_lower:
                intent = "cultural_immersion"
            elif "luxury" in query_lower or "premium" in query_lower or "exclusive" in query_lower:
                intent = "luxury_experiences"
            elif "romantic" in query_lower or "couples" in query_lower or "date" in query_lower:
                intent = "romantic_dates"
            else:
                # Use regular search with the query if no intent detected
                return await _mongodb_search(
                    db, q, None, area, None, None, None, None,
                    None, None, None, None, None,
                    page, per_page, "relevance"
                )
        
        # If no intent provided and no query, return error
        if not intent:
            raise HTTPException(status_code=400, detail="Either 'intent' or 'q' parameter is required")
        
        # Get intent configuration
        intent_config = intent_mappings.get(intent)
        if not intent_config:
            # If intent not found, try to use it as a search query
            return await _mongodb_search(
                db, intent, None, area, None, None, None, None,
                None, None, None, None, None,
                page, per_page, "relevance"
            )
        
        # Build search query based on intent
        filter_query = {"status": "active"}
        
        # Add tag filters
        if "tags" in intent_config:
            filter_query["tags"] = {"$in": intent_config["tags"]}
        
        # Add category filter
        if "category" in intent_config:
            filter_query["category"] = intent_config["category"]
        
        # Add price filter
        if "price_max" in intent_config:
            filter_query["pricing.base_price"] = {"$lte": intent_config["price_max"]}
        
        # Add date filter for time-based intents
        if "date_filter" in intent_config:
            date_filter_type = intent_config["date_filter"]
            if date_filter_type == "today":
                # Events happening today
                from datetime import datetime
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                tomorrow = today.replace(hour=23, minute=59, second=59)
                filter_query["$and"] = filter_query.get("$and", [])
                filter_query["$and"].extend([
                    {"start_date": {"$gte": today}},
                    {"start_date": {"$lte": tomorrow}}
                ])
            elif date_filter_type == "weekend":
                # Events happening this weekend (Saturday and Sunday)
                from datetime import datetime, timedelta
                now = datetime.now()
                days_until_saturday = (5 - now.weekday()) % 7  # Saturday is 5 (Monday = 0)
                if days_until_saturday == 0 and now.hour >= 18:  # If it's Saturday evening, look at next weekend
                    days_until_saturday = 7
                saturday = (now + timedelta(days=days_until_saturday)).replace(hour=0, minute=0, second=0, microsecond=0)
                sunday_end = saturday.replace(hour=23, minute=59, second=59) + timedelta(days=1)
                filter_query["$and"] = filter_query.get("$and", [])
                filter_query["$and"].extend([
                    {"start_date": {"$gte": saturday}},
                    {"start_date": {"$lte": sunday_end}}
                ])
        
        # Add family-friendly filter
        if "family_friendly" in intent_config:
            family_or = [
                {"familySuitability.isAllAges": True},
                {"tags": {"$in": ["family-friendly", "kids", "children"]}}
            ]
            
            if "$and" in filter_query:
                filter_query["$and"].append({"$or": family_or})
            else:
                filter_query["$or"] = family_or
        
        # Add area filter if provided
        if area:
            area_filter = {"venue.area": {"$regex": f".*{re.escape(area)}.*", "$options": "i"}}
            
            if "$and" in filter_query:
                filter_query["$and"].append(area_filter)
            elif "$or" in filter_query:
                # Combine with existing OR query
                existing_or = filter_query.pop("$or")
                filter_query["$and"] = [
                    {"$or": existing_or},
                    area_filter
                ]
            else:
                filter_query.update(area_filter)
        
        # Execute search with smart sorting
        skip = (page - 1) * per_page
        
        # Smart sorting based on intent
        sort_criteria = [("start_date", 1)]  # Default
        
        if intent in ["luxury_experiences"]:
            sort_criteria = [("pricing.base_price", -1), ("rating", -1)]
        elif intent in ["budget_friendly", "find_free_events"]:
            sort_criteria = [("pricing.base_price", 1), ("rating", -1)]
        elif intent in ["weekend_family_fun", "kids_activities"]:
            sort_criteria = [("familyScore", -1), ("rating", -1)]
        elif intent in ["cultural_immersion"]:
            sort_criteria = [("rating", -1), ("start_date", 1)]
        
        events_cursor = db.events.find(filter_query).sort(sort_criteria).skip(skip).limit(per_page)
        events = await events_cursor.to_list(length=per_page)
        
        # Get total count
        total = await db.events.count_documents(filter_query)
        
        # Convert to response format
        event_responses = []
        for event in events:
            event_responses.append(await _convert_event_to_response(event))
        
        return {
            "events": event_responses,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page,
                "has_next": skip + per_page < total,
                "has_prev": page > 1,
                "search_description": intent_config.get("description", "Search results")
            },
            "filters": await _get_filter_options(db)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Smart search error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Smart search failed. Please try again.")


# Helper functions for search implementation

async def _elasticsearch_search(
    es: AsyncElasticsearch, query: str, category: Optional[str], area: Optional[str],
    date_from: Optional[str], date_to: Optional[str], price_max: Optional[float],
    price_min: Optional[float], age_group: Optional[str], family_friendly: Optional[bool],
    latitude: Optional[float], longitude: Optional[float], radius_km: Optional[float],
    page: int, per_page: int, sort_by: str
) -> Optional[dict]:
    """
    Perform Elasticsearch search (when available)
    """
    try:
        # Build Elasticsearch query
        must_clauses = []
        filter_clauses = [{"term": {"status": "active"}}]
        
        # Enhanced text search with comprehensive tag support
        if query:
            must_clauses.append({
                "bool": {
                    "should": [
                        # Exact tag matches (highest boost)
                        {
                            "terms": {
                                "tags": [query.lower()],
                                "boost": 20
                            }
                        },
                        # Partial tag matches
                        {
                            "wildcard": {
                                "tags": {
                                    "value": f"*{query.lower()}*",
                                    "boost": 15
                                }
                            }
                        },
                        # Enhanced multi-field search
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "title^10",           # Highest priority
                                    "category^8",         # High priority for categories
                                    "tags^12",            # Very high priority for tags
                                    "venue.name^6",       # Medium-high priority
                                    "venue.area^5",       # Medium priority
                                    "description^3",      # Lower priority
                                    "shortDescription^4"  # Medium-low priority
                                ],
                                "type": "best_fields",
                                "fuzziness": "AUTO",
                                "boost": 5
                            }
                        },
                        # Category-specific boosts
                        {
                            "bool": {
                                "should": [
                                    {
                                        "bool": {
                                            "must": [
                                                {"term": {"category": "food_and_dining"}},
                                                {"terms": {"tags": ["food", "dining", "restaurant", "brunch", "buffet"]}}
                                            ],
                                            "boost": 8
                                        }
                                    },
                                    {
                                        "bool": {
                                            "must": [
                                                {"term": {"category": "indoor_activities"}},
                                                {"terms": {"tags": ["indoor", "mall", "museum", "gallery", "air-conditioned"]}}
                                            ],
                                            "boost": 8
                                        }
                                    },
                                    {
                                        "bool": {
                                            "must": [
                                                {"term": {"category": "kids_and_family"}},
                                                {"terms": {"tags": ["family-friendly", "kids", "children", "educational"]}}
                                            ],
                                            "boost": 8
                                        }
                                    }
                                ]
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            })
        
        # Category filter
        if category:
            filter_clauses.append({"term": {"category_tags": category}})
        
        # Area filter
        if area:
            filter_clauses.append({"wildcard": {"area": f"*{area}*"}})
        
        # Date range filter
        date_range = {}
        if date_from:
            date_range["gte"] = date_from
        if date_to:
            date_range["lte"] = date_to
        if date_range:
            filter_clauses.append({"range": {"start_date": date_range}})
        
        # Price range filter
        price_range = {}
        if price_min is not None:
            price_range["gte"] = price_min
        if price_max is not None:
            price_range["lte"] = price_max
        if price_range:
            filter_clauses.append({"range": {"price_min": price_range}})
        
        # Family friendly filter
        if family_friendly is not None:
            filter_clauses.append({"term": {"is_family_friendly": family_friendly}})
        
        # Geospatial filter
        if latitude is not None and longitude is not None:
            filter_clauses.append({
                "geo_distance": {
                    "distance": f"{radius_km}km",
                    "location": {"lat": latitude, "lon": longitude}
                }
            })
        
        # Build sort
        sort_options = []
        if sort_by == "relevance" and query:
            sort_options.append({"_score": {"order": "desc"}})
        elif sort_by == "start_date":
            sort_options.append({"start_date": {"order": "asc"}})
        elif sort_by == "price":
            sort_options.append({"price_min": {"order": "asc"}})
        elif sort_by == "family_score":
            sort_options.append({"family_score": {"order": "desc"}})
        
        # Default sort
        if not sort_options:
            sort_options.append({"start_date": {"order": "asc"}})
        
        # Build complete query
        es_query = {
            "query": {
                "bool": {
                    "must": must_clauses,
                    "filter": filter_clauses
                }
            },
            "sort": sort_options,
            "from": (page - 1) * per_page,
            "size": per_page
        }
        
        # Execute search
        result = await es.search(index="events", body=es_query)
        
        # Convert results
        events = []
        for hit in result["hits"]["hits"]:
            source = hit["_source"]
            source["_id"] = hit["_id"]
            events.append(await _convert_event_to_response(source))
        
        total = result["hits"]["total"]["value"]
        
        return {
            "events": events,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page,
                "has_next": (page - 1) * per_page + per_page < total,
                "has_prev": page > 1
            },
            "filters": {}  # Will be populated by caller
        }
        
    except Exception as e:
        print(f"Elasticsearch search error: {e}")
        return None


async def _mongodb_search(
    db: AsyncIOMotorDatabase, query: str, category: Optional[str], area: Optional[str],
    date_from: Optional[str], date_to: Optional[str], price_max: Optional[float],
    price_min: Optional[float], age_group: Optional[str], family_friendly: Optional[bool],
    latitude: Optional[float], longitude: Optional[float], radius_km: Optional[float],
    page: int, per_page: int, sort_by: str
) -> dict:
    """
    MongoDB search using aggregation pipeline for better control
    """
    try:
        logger.info(f"MongoDB search called with query='{query}', category='{category}', area='{area}'")
        
        # Build aggregation pipeline
        pipeline = []
        
        # Stage 1: Base match for active events
        match_stage = {"status": "active"}
        
        # Add text search if query provided
        if query:
            query_lower = query.lower().strip()
            logger.info(f"Adding text search for: '{query_lower}'")
            
            # Use OR for text matching across multiple fields
            match_stage["$or"] = [
                {"title": {"$regex": f".*{re.escape(query_lower)}.*", "$options": "i"}},
                {"tags": {"$regex": f".*{re.escape(query_lower)}.*", "$options": "i"}},
                {"category": {"$regex": f".*{re.escape(query_lower)}.*", "$options": "i"}},
                {"venue.name": {"$regex": f".*{re.escape(query_lower)}.*", "$options": "i"}},
                {"venue.area": {"$regex": f".*{re.escape(query_lower)}.*", "$options": "i"}},
                {"description": {"$regex": f".*{re.escape(query_lower)}.*", "$options": "i"}}
            ]
        
        pipeline.append({"$match": match_stage})
        
        # Stage 2: Additional filters as separate match stages
        if category:
            logger.info(f"Adding category filter: {category}")
            pipeline.append({"$match": {"category": category}})
        
        if area:
            logger.info(f"Adding area filter: {area}")
            pipeline.append({"$match": {"venue.area": {"$regex": f".*{re.escape(area)}.*", "$options": "i"}}})
        
        if family_friendly is not None:
            logger.info(f"Adding family filter: {family_friendly}")
            if family_friendly:
                pipeline.append({"$match": {"familySuitability.isAllAges": True}})
            else:
                pipeline.append({"$match": {"familySuitability.isAllAges": {"$ne": True}}})
        
        if price_min is not None or price_max is not None:
            logger.info(f"Adding price filter: min={price_min}, max={price_max}")
            price_match = {}
            if price_min is not None:
                price_match["pricing.base_price"] = {"$gte": price_min}
            if price_max is not None:
                if "pricing.base_price" in price_match:
                    price_match["pricing.base_price"]["$lte"] = price_max
                else:
                    price_match["pricing.base_price"] = {"$lte": price_max}
            if price_match:
                pipeline.append({"$match": price_match})
        
        if date_from or date_to:
            logger.info(f"Adding date filter: from={date_from}, to={date_to}")
            date_match = {}
            try:
                if date_from:
                    date_match["start_date"] = {"$gte": datetime.fromisoformat(date_from.replace('Z', '+00:00'))}
                if date_to:
                    if "start_date" in date_match:
                        date_match["start_date"]["$lte"] = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                    else:
                        date_match["start_date"] = {"$lte": datetime.fromisoformat(date_to.replace('Z', '+00:00'))}
                if date_match:
                    pipeline.append({"$match": date_match})
            except ValueError as e:
                logger.warning(f"Invalid date format: {e}, skipping date filter")
        
        # Stage 3: Add relevance score if searching
        if query and sort_by == "relevance":
            logger.info("Adding relevance scoring")
            pipeline.append({
                "$addFields": {
                    "relevance_score": {
                        "$sum": [
                            {"$cond": [{"$regexMatch": {"input": "$title", "regex": re.escape(query_lower), "options": "i"}}, 10, 0]},
                            {"$cond": [{"$regexMatch": {"input": {"$ifNull": ["$category", ""]}, "regex": re.escape(query_lower), "options": "i"}}, 5, 0]},
                            {"$cond": [{"$in": [query_lower, {"$ifNull": ["$tags", []]}]}, 8, 0]},
                            {"$cond": [{"$regexMatch": {"input": {"$ifNull": ["$venue.name", ""]}, "regex": re.escape(query_lower), "options": "i"}}, 3, 0]}
                        ]
                    }
                }
            })
        
        # Stage 4: Sorting
        sort_stage = {}
        if query and sort_by == "relevance":
            sort_stage = {"relevance_score": -1, "start_date": 1}
        elif sort_by == "start_date":
            sort_stage = {"start_date": 1}
        elif sort_by == "price":
            sort_stage = {"pricing.base_price": 1}
        elif sort_by == "family_score":
            sort_stage = {"familyScore": -1}
        elif sort_by == "rating":
            sort_stage = {"rating": -1}
        else:
            sort_stage = {"start_date": 1}
        
        pipeline.append({"$sort": sort_stage})
        
        # Stage 5: Facet for pagination
        skip = (page - 1) * per_page
        pipeline.append({
            "$facet": {
                "events": [
                    {"$skip": skip},
                    {"$limit": per_page}
                ],
                "totalCount": [
                    {"$count": "count"}
                ]
            }
        })
        
        logger.info(f"Executing aggregation pipeline with {len(pipeline)} stages")
        logger.debug(f"Pipeline: {pipeline}")
        
        # Execute aggregation
        result = await db.events.aggregate(pipeline).to_list(1)
        
        if result and len(result) > 0:
            events = result[0].get("events", [])
            total_count = result[0].get("totalCount", [])
            total = total_count[0]["count"] if total_count else 0
            
            logger.info(f"Aggregation complete: found {len(events)} events out of {total} total")
        else:
            logger.warning("Aggregation returned no results")
            events = []
            total = 0
        
        # Convert to response format
        event_responses = []
        for event in events:
            try:
                event_responses.append(await _convert_event_to_response(event))
            except Exception as e:
                logger.warning(f"Error converting event {event.get('_id')}: {e}")
                continue
        
        # Return simple response structure
        return {
            "events": event_responses,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page,
                "has_next": (page - 1) * per_page + per_page < total,
                "has_prev": page > 1
            },
            "filters": await _get_filter_options(db)
        }
    except Exception as e:
        logger.error(f"MongoDB search error: {str(e)}\n{traceback.format_exc()}")
        # Return empty results on error
        return {
            "events": [],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": 0,
                "total_pages": 0,
                "has_next": False,
                "has_prev": False
            },
            "filters": await _get_filter_options(db)
        } 