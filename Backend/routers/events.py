"""Event management router for DXB Events API.

Phase 2: Search & Discovery implementation.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
import random

from database import get_mongodb
from schemas import (
    EventResponse, EventListResponse
)
from utils.deduplication import EventDeduplicator
from utils.date_utils import calculate_date_range
# from utils.rate_limiting import search_rate_limit  # Optional
# from routers.auth import get_current_user  # Removed PostgreSQL auth
# from models.postgres_models import User  # Removed PostgreSQL models

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/search-titles", response_model=list[str])
async def search_event_titles(
    query: str = Query(..., min_length=1, description="Search query for event titles"),
    limit: int = Query(10, ge=1, le=20, description="Number of suggestions to return"),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Search event titles based on query for autocomplete suggestions
    """
    if not query or len(query.strip()) < 1:
        return []
    
    # Build MongoDB text search with regex for partial matching
    search_query = {
        "status": "active",
        "end_date": {"$gte": datetime.utcnow()},  # Only active events
        "$or": [
            {"title": {"$regex": f".*{query}.*", "$options": "i"}},
            {"description": {"$regex": f".*{query}.*", "$options": "i"}},
            {"category": {"$regex": f".*{query}.*", "$options": "i"}},
            {"tags": {"$in": [{"$regex": f".*{query}.*", "$options": "i"}]}},
            {"venue.name": {"$regex": f".*{query}.*", "$options": "i"}},
            {"venue.area": {"$regex": f".*{query}.*", "$options": "i"}}
        ]
    }
    
    try:
        # Find matching events and project only titles
        events_cursor = db.events.find(
            search_query,
            {"title": 1, "_id": 0}
        ).limit(limit)
        
        events = await events_cursor.to_list(length=limit)
        
        # Extract unique titles
        titles = [event["title"] for event in events if "title" in event]
        
        # Remove duplicates while preserving order
        unique_titles = []
        seen = set()
        for title in titles:
            if title.lower() not in seen:
                unique_titles.append(title)
                seen.add(title.lower())
        
        return unique_titles[:limit]
        
    except Exception as e:
        print(f"Error searching event titles: {e}")
        return []


@router.get("/", response_model=EventListResponse)
async def get_events(
    category: Optional[str] = Query(None, description="Filter by category"),
    location: Optional[str] = Query(None, description="Filter by location/area"),
    area: Optional[str] = Query(None, description="Dubai area (Marina, JBR, etc.)"),
    date_from: Optional[datetime] = Query(None, description="Events from this date"),
    date_to: Optional[datetime] = Query(None, description="Events until this date"),
    date_filter: Optional[str] = Query(None, description="Predefined date filter: today, tomorrow, this_week, next_week, this_weekend, next_weekend, this_month, next_month"),
    date_range: Optional[str] = Query(None, description="Alias for date_filter (for frontend compatibility)"),
    price_max: Optional[float] = Query(None, description="Maximum price in AED"),
    price_min: Optional[float] = Query(None, description="Minimum price in AED"),
    age_group: Optional[str] = Query(None, description="Age group (child, teen, adult, family)"),
    family_friendly: Optional[bool] = Query(None, description="Family friendly events only"),
    latitude: Optional[float] = Query(None, description="Latitude for distance search"),
    longitude: Optional[float] = Query(None, description="Longitude for distance search"),
    radius_km: Optional[float] = Query(10, description="Search radius in kilometers"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("start_date", description="Sort by: start_date, price, family_score, distance"),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
    # rate_limit: bool = Depends(search_rate_limit)  # Temporarily disabled
):
    """
    Get paginated list of events with filtering and sorting
    """
    # Build MongoDB filter query
    filter_query = {"status": "active"}
    
    # Always filter out past events (events must end today or later)
    # This includes ongoing multi-day events and future events
    current_time = datetime.utcnow()
    
    # Handle predefined date filters (today, this_week, etc.)
    # Support both date_filter and date_range parameters for compatibility
    active_date_filter = date_filter or date_range
    if active_date_filter and active_date_filter.lower() != 'all':
        try:
            filter_start, filter_end = calculate_date_range(active_date_filter)
            # For predefined filters, we want events that overlap with the date range
            # This means events that start before the range ends AND end after the range starts
            # Remove the general end_date filter since we're using specific date range
            filter_query.pop("end_date", None)
            filter_query["$and"] = [
                {"start_date": {"$lte": filter_end}},
                {"end_date": {"$gte": filter_start}}
            ]
        except Exception as e:
            print(f"Error processing date filter '{active_date_filter}': {e}")
            # Fall back to default filtering if there's an error
            filter_query["end_date"] = {"$gte": current_time}
    else:
        # Only apply general filter if no date_filter is specified
        filter_query["end_date"] = {"$gte": current_time}
    
    # Additional date filtering from parameters for start_date
    if date_from or date_to:
        start_date_filter = {}
        if date_from:
            start_date_filter["$gte"] = date_from
        if date_to:
            start_date_filter["$lte"] = date_to
        filter_query["start_date"] = start_date_filter
    
        # Price filtering - work with your actual price structure
    if price_min is not None or price_max is not None:
        # Since price is stored as string or in price_data, we'll use a more flexible approach
        # For now, we'll skip complex price filtering and just check for "free" events
        if price_min == 0 and price_max == 0:
            # Looking for free events
            filter_query["$or"] = [
                {"price": {"$regex": "free", "$options": "i"}},
                {"price_data.min": 0},
                {"price_data.max": 0}
            ]

    # Category filtering - use tags since category might not be populated
    if category:
        filter_query["$or"] = [
            {"category": category},
            {"tags": {"$in": [category]}}
        ]

    # Area filtering - search in location string since area isn't extracted yet
    if area:
        filter_query["location"] = {"$regex": area, "$options": "i"}
    
    # Family friendly filtering
    if family_friendly is not None:
        filter_query["is_family_friendly"] = family_friendly
    
    # Age group filtering
    if age_group:
        age_ranges = {
            "child": {"age_min": {"$lte": 12}, "age_max": {"$gte": 0}},
            "teen": {"age_min": {"$lte": 18}, "age_max": {"$gte": 13}},
            "adult": {"age_min": {"$lte": 99}, "age_max": {"$gte": 18}},
            "family": {"is_family_friendly": True}
        }
        if age_group in age_ranges:
            filter_query.update(age_ranges[age_group])
    
    # Location/distance filtering (if coordinates provided)
    if latitude is not None and longitude is not None:
        filter_query["location"] = {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [longitude, latitude]},
                "$maxDistance": radius_km * 1000  # Convert to meters
            }
        }
    
    # Build sort query
    sort_options = {
        "start_date": [("start_date", 1)],
        "price": [("price_min", 1)],
        "family_score": [("family_score", -1)],
        "distance": [("location", 1)] if latitude and longitude else [("start_date", 1)]
    }
    sort_query = sort_options.get(sort_by, [("start_date", 1)])
    
    # Calculate pagination
    skip = (page - 1) * per_page
    
    # Execute queries
    events_cursor = db.events.find(filter_query).sort(sort_query).skip(skip).limit(per_page)
    events = await events_cursor.to_list(length=per_page)
    
    # Get total count for pagination
    total = await db.events.count_documents(filter_query)
    
    # Convert to response format
    event_responses = []
    for event in events:
        event_responses.append(await _convert_event_to_response(event))
    
    # Get filter options
    filter_options = await _get_filter_options(db)
    
    return EventListResponse(
        events=event_responses,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
            "has_next": skip + per_page < total,
            "has_prev": page > 1
        },
        filters=filter_options
    )


@router.get("/trending", response_model=dict)
async def get_trending_events_enhanced(
    limit: int = Query(20, ge=1, le=50),
    enhanced: bool = Query(False),
    include_quality_metrics: bool = Query(False),
    include_social_media: bool = Query(False),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Get trending events with enhanced features for frontend compatibility
    This endpoint supports the enhanced_events_service.dart call
    """
    current_date = datetime.utcnow()
    filter_query = {
        "status": "active", 
        "end_date": {"$gte": current_date},
        "start_date": {"$lte": current_date.replace(hour=23, minute=59, second=59) + timedelta(days=90)}  # Events within next 90 days
    }
    
    # Prioritize firecrawl extracted events for quality
    if enhanced:
        filter_query["extraction_method"] = "firecrawl"
    
    # Get a larger pool of trending events to shuffle from
    pool_size = min(limit * 3, 100)  # Get 3x the requested amount, max 100
    
    # Sort by trending score (view_count + save_count * 2)
    pipeline = [
        {"$match": filter_query},
        {"$addFields": {
            "trending_score": {"$add": [{"$ifNull": ["$view_count", 0]}, {"$multiply": [{"$ifNull": ["$save_count", 0]}, 2]}]}
        }},
        {"$sort": {"trending_score": -1}},
        {"$limit": pool_size}
    ]
    
    events = await db.events.aggregate(pipeline).to_list(length=pool_size)
    
    # Daily rotation logic removed to allow for more dynamic trending events
    # The frontend will handle any desired randomization or diversity
    
    event_responses = []
    for event in events:
        event_responses.append(await _convert_event_to_response(event))
    
    return {
        "success": True,
        "events": event_responses,
        "total": len(event_responses),
        "message": "Trending events retrieved successfully"
    }


@router.get("/firecrawl/list", response_model=EventListResponse)
async def get_firecrawl_events(
    limit: int = Query(20, ge=1, le=100),
    area: Optional[str] = Query(None),
    sort_by: str = Query("trending_score", description="Sort by: trending_score, start_date, family_score"),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Get firecrawl-extracted events (high-quality verified events)
    This endpoint supports the frontend's getFirecrawlEvents call
    """
    filter_query = {
        "status": "active",
        "end_date": {"$gte": datetime.utcnow()},
        "extraction_method": "firecrawl"
    }
    
    if area:
        filter_query["venue.area"] = {"$regex": area, "$options": "i"}
    
    # Determine sort order
    sort_field = "start_date"
    if sort_by == "trending_score":
        # Use aggregation pipeline for trending score
        pipeline = [
            {"$match": filter_query},
            {"$addFields": {
                "trending_score": {"$add": [{"$ifNull": ["$view_count", 0]}, {"$multiply": [{"$ifNull": ["$save_count", 0]}, 2]}]}
            }},
            {"$sort": {"trending_score": -1}},
            {"$limit": limit}
        ]
        events = await db.events.aggregate(pipeline).to_list(length=limit)
    elif sort_by == "family_score":
        sort_field = "family_score"
        events = await db.events.find(filter_query).sort([(sort_field, -1)]).limit(limit).to_list(length=limit)
    else:
        events = await db.events.find(filter_query).sort([(sort_field, 1)]).limit(limit).to_list(length=limit)
    
    event_responses = []
    for event in events:
        event_responses.append(await _convert_event_to_response(event))
    
    return EventListResponse(
        events=event_responses,
        total=len(events),
        page=1,
        per_page=limit,
        total_pages=1,
        pagination={"page": 1, "per_page": limit, "total": len(events), "total_pages": 1, "has_next": False, "has_prev": False},
        filters=await _get_filter_options(db)
    )


@router.get("/saved/list", response_model=EventListResponse)
async def get_saved_events(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    # current_user: User = Depends(get_current_user),  # Temporarily disabled
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Get user's saved events
    """
    # TODO: Implement fetching from PostgreSQL user_events table
    # For now, return empty list
    return EventListResponse(
        events=[],
        pagination={"page": 1, "per_page": 20, "total": 0, "total_pages": 0, "has_next": False, "has_prev": False},
        filters={"categories": [], "areas": [], "price_ranges": [], "age_groups": []}
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    # current_user: Optional[User] = Depends(get_current_user),  # Temporarily disabled
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Get detailed event information by ID
    """
    if not ObjectId.is_valid(event_id):
        raise HTTPException(status_code=400, detail="Invalid event ID format")
    
    event = await db.events.find_one({"_id": ObjectId(event_id)})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Increment view count
    await db.events.update_one(
        {"_id": ObjectId(event_id)},
        {"$inc": {"view_count": 1}}
    )
    
    # Check if user has saved this event
    is_saved = False
    # TODO: Implement user authentication and saved events checking
    # if current_user:
    #     # Check in PostgreSQL user_events table (you'll need to implement this)
    #     pass
    
    return await _convert_event_to_response(event, is_saved=is_saved)


@router.get("/trending/list", response_model=EventListResponse)
async def get_trending_events(
    limit: int = Query(10, ge=1, le=50),
    area: Optional[str] = Query(None),
    firecrawl_only: bool = Query(False),
    extraction_method: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Get trending events based on view count and save count
    """
    current_date = datetime.utcnow()
    filter_query = {
        "status": "active", 
        "end_date": {"$gte": current_date},
        "start_date": {"$lte": current_date.replace(hour=23, minute=59, second=59) + timedelta(days=90)}  # Events within next 90 days
    }
    
    if area:
        filter_query["venue.area"] = {"$regex": area, "$options": "i"}
    
    # Prioritize firecrawl extracted events for quality
    if firecrawl_only:
        filter_query["extraction_method"] = "firecrawl"
    elif extraction_method:
        filter_query["extraction_method"] = extraction_method
    
    # Get a larger pool of trending events to shuffle from
    pool_size = min(limit * 3, 100)  # Get 3x the requested amount, max 100
    
    # Sort by trending score (view_count + save_count * 2)
    pipeline = [
        {"$match": filter_query},
        {"$addFields": {
            "trending_score": {"$add": [{"$ifNull": ["$view_count", 0]}, {"$multiply": [{"$ifNull": ["$save_count", 0]}, 2]}]}
        }},
        {"$sort": {"trending_score": -1}},
        {"$limit": pool_size}
    ]
    
    events = await db.events.aggregate(pipeline).to_list(length=pool_size)
    
    # Use daily rotation like MyDscvr's Choice to ensure different events each day
    # This provides deterministic variety while still selecting from high-quality trending events
    if len(events) > limit:
        # Get day of year for rotation
        day_of_year = datetime.utcnow().timetuple().tm_yday
        
        # Rotate starting position based on day
        # This ensures we show different events each day while maintaining quality
        rotation_offset = (day_of_year * limit) % len(events)
        
        # Create a rotated list starting from the offset
        rotated_events = events[rotation_offset:] + events[:rotation_offset]
        
        # Take the first 'limit' events from the rotated list
        events = rotated_events[:limit]
    
    event_responses = []
    for event in events:
        event_responses.append(await _convert_event_to_response(event))
    
    return EventListResponse(
        events=event_responses,
        total=len(event_responses),
        page=1,
        per_page=limit,
        total_pages=1,
        pagination={"page": 1, "per_page": limit, "total": len(event_responses), "total_pages": 1, "has_next": False, "has_prev": False},
        filters=await _get_filter_options(db)
    )


@router.get("/featured/list", response_model=EventListResponse)
async def get_featured_events(
    limit: int = Query(12, ge=1, le=50),
    area: Optional[str] = Query(None),
    ai_images_only: bool = Query(False, description="Only return events that have an AI-generated image"),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Get featured events using enhanced algorithm that considers:
    1. Extraction method quality (firecrawl > perplexity > others)
    2. Family score 
    3. Date proximity
    4. AI image availability (if requested)
    """
    filter_query = {
        "status": "active",
        "end_date": {"$gte": datetime.utcnow()}
    }
    
    if area:
        filter_query["venue.area"] = {"$regex": area, "$options": "i"}

    # If ai_images_only is True, add a filter for events with AI-generated images
    if ai_images_only:
        filter_query["images.ai_generated"] = {"$exists": True, "$ne": None, "$ne": ""}

    
    # Enhanced scoring pipeline with extraction method priority
    pipeline = [
        {"$match": filter_query},
        {"$addFields": {
            "days_until_event": {
                "$divide": [
                    {"$subtract": ["$start_date", datetime.utcnow()]},
                    86400000  # milliseconds in a day
                ]
            }
        }},
        {"$addFields": {
            "date_proximity_score": {
                "$switch": {
                    "branches": [
                        {"case": {"$lte": ["$days_until_event", 0]}, "then": 0},
                        {"case": {"$lte": ["$days_until_event", 1]}, "then": 30},
                        {"case": {"$lte": ["$days_until_event", 3]}, "then": 25},
                        {"case": {"$lte": ["$days_until_event", 7]}, "then": 20},
                        {"case": {"$lte": ["$days_until_event", 30]}, "then": 15}
                    ],
                    "default": 10
                }
            }
        }},
        {"$addFields": {
            "extraction_quality_score": {
                "$switch": {
                    "branches": [
                        {"case": {"$eq": ["$extraction_method", "firecrawl"]}, "then": 30},
                        {"case": {"$eq": ["$extraction_method", "perplexity"]}, "then": 20},
                        {"case": {"$eq": ["$extraction_method", "hybrid"]}, "then": 25}
                    ],
                    "default": 10
                }
            }
        }},
        {"$addFields": {
            "ai_image_score": {
                "$cond": {
                    "if": {
                        "$or": [
                            {"$gt": [{"$ifNull": ["$images.ai_generated", None]}, None]},
                            {"$gt": [{"$ifNull": ["$ai_image_url", None]}, None]}
                        ]
                    },
                    "then": 50,
                    "else": 0
                }
            }
        }},
        {"$addFields": {
            "featured_score": {
                "$add": [
                    {"$multiply": ["$ai_image_score", 0.5]},
                    {"$multiply": ["$extraction_quality_score", 0.25]},
                    {"$multiply": [{"$ifNull": ["$family_score", 75]}, 0.15]},
                    {"$multiply": ["$date_proximity_score", 0.10]}
                ]
            }
        }},
        {"$sort": {"featured_score": -1, "start_date": 1}},
        {"$limit": limit}
    ]
    
    events = await db.events.aggregate(pipeline).to_list(length=limit)
    
    # Apply deduplication to featured events
    deduplicated_events = []
    seen_titles = set()
    
    for event in events:
        # Simple title-based deduplication for featured events
        title_normalized = event.get('title', '').lower().strip()
        if title_normalized not in seen_titles:
            deduplicated_events.append(event)
            seen_titles.add(title_normalized)
        else:
            print(f"🔄 Featured Events: Skipped duplicate - {event.get('title', 'Unknown')}")
    
    print(f"🔄 Featured Events: {len(events)} events before deduplication, {len(deduplicated_events)} after")
    
    event_responses = []
    for event in deduplicated_events:
        event_responses.append(await _convert_event_to_response(event))
    
    return EventListResponse(
        events=event_responses,
        total=len(deduplicated_events),
        page=1,
        per_page=limit,
        total_pages=1,
        pagination={"page": 1, "per_page": limit, "total": len(deduplicated_events), "total_pages": 1, "has_next": False, "has_prev": False},
        filters=await _get_filter_options(db)
    )


@router.get("/mydscvr-choice", response_model=EventResponse)
async def get_mydscvr_choice(
    area: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Get MyDscvr's daily curated choice event with maximum priority for firecrawl events
    """
    filter_query = {
        "status": "active",
        "end_date": {"$gte": datetime.utcnow()}
    }
    
    if area:
        filter_query["venue.area"] = {"$regex": area, "$options": "i"}
    
    # Enhanced scoring pipeline with maximum firecrawl priority
    pipeline = [
        {"$match": filter_query},
        {"$addFields": {
            "days_until_event": {
                "$divide": [
                    {"$subtract": ["$start_date", datetime.utcnow()]},
                    86400000  # milliseconds in a day
                ]
            }
        }},
        {"$addFields": {
            "date_proximity_score": {
                "$switch": {
                    "branches": [
                        {"case": {"$lte": ["$days_until_event", 0]}, "then": 0},
                        {"case": {"$lte": ["$days_until_event", 1]}, "then": 30},
                        {"case": {"$lte": ["$days_until_event", 3]}, "then": 25},
                        {"case": {"$lte": ["$days_until_event", 7]}, "then": 20},
                        {"case": {"$lte": ["$days_until_event", 30]}, "then": 15}
                    ],
                    "default": 10
                }
            }
        }},
        {"$addFields": {
            "extraction_quality_score": {
                "$switch": {
                    "branches": [
                        {"case": {"$eq": ["$extraction_method", "firecrawl"]}, "then": 50},  # Maximum priority
                        {"case": {"$eq": ["$extraction_method", "hybrid"]}, "then": 25},
                        {"case": {"$eq": ["$extraction_method", "perplexity"]}, "then": 15}
                    ],
                    "default": 5
                }
            }
        }},
        {"$addFields": {
            "mydscvr_choice_score": {
                "$add": [
                    {"$multiply": [{"$ifNull": ["$family_score", 75]}, 0.3]},
                    {"$multiply": ["$date_proximity_score", 0.2]},
                    {"$multiply": ["$extraction_quality_score", 0.5]}  # 50% weight for extraction quality
                ]
            }
        }},
        {"$sort": {"mydscvr_choice_score": -1, "start_date": 1}},
        {"$limit": 1}
    ]
    
    events = await db.events.aggregate(pipeline).to_list(length=1)
    
    if not events:
        raise HTTPException(status_code=404, detail="No suitable events found for MyDscvr's Choice")
    
    # Increment view count for the chosen event
    event = events[0]
    await db.events.update_one(
        {"_id": event["_id"]},
        {"$inc": {"view_count": 1}}
    )
    
    return await _convert_event_to_response(event)


@router.get("/recommendations/family", response_model=EventListResponse)
async def get_family_recommendations(
    limit: int = Query(10, ge=1, le=50),
    # current_user: User = Depends(get_current_user),  # Temporarily disabled
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Get personalized family event recommendations
    """
    # TODO: Implement sophisticated recommendation logic based on:
    # - User's family members ages
    # - Previously saved events
    # - Location preferences
    # - Budget range
    
    # For now, return family-friendly events with high family scores
    filter_query = {
        "status": "active",
        "end_date": {"$gte": datetime.utcnow()}
        # Made less restrictive since family_score and is_family_friendly might not exist
    }
    
    events = await db.events.find(filter_query).sort([("start_date", 1)]).limit(limit).to_list(length=limit)
    
    event_responses = []
    for event in events:
        event_responses.append(await _convert_event_to_response(event))
    
    return EventListResponse(
        events=event_responses,
        total=len(events),
        page=1,
        per_page=limit,
        total_pages=1,
        pagination={"page": 1, "per_page": limit, "total": len(events), "total_pages": 1, "has_next": False, "has_prev": False},
        filters=await _get_filter_options(db)
    )


# Helper functions
async def _convert_event_to_response(event: dict, is_saved: bool = False) -> EventResponse:
    """Convert MongoDB event document to EventResponse"""
    
    # Extract venue information from available fields
    venue_info = None
    venue_field = event.get("venue")
    
    if isinstance(venue_field, dict):
        # Venue is already properly structured
        venue_name = venue_field.get("name", "Event Venue")
        venue_area = venue_field.get("area")
        venue_address = venue_field.get("address")
        
        # Ensure all fields are strings or None
        # Fix area if it's "unknown" - try to extract from address or use fallback
        if venue_area == "unknown" or not venue_area:
            # Try to extract area from address or use Dubai as fallback
            if venue_address and "dubai" in venue_address.lower():
                # Look for common Dubai areas in address
                dubai_areas = ["marina", "downtown", "jbr", "business bay", "bur dubai", "deira", "jumeirah", "mall of emirates", "dubai mall"]
                venue_area = "Dubai"  # Default fallback
                for area in dubai_areas:
                    if area in venue_address.lower():
                        venue_area = area.title()
                        break
            else:
                venue_area = "Dubai"  # Default fallback
        
        venue_info = {
            "name": str(venue_name) if venue_name else "Event Venue",
            "area": str(venue_area) if venue_area else "Dubai",
            "address": str(venue_address) if venue_address else None,
            "amenities": {}
        }
        # Add coordinates if available
        coords = venue_field.get("coordinates", {})
        if coords and isinstance(coords, dict):
            lat = coords.get("lat")
            lng = coords.get("lng")
            if lat is not None:
                venue_info["latitude"] = float(lat)
            if lng is not None:
                venue_info["longitude"] = float(lng)
    else:
        # Fallback: extract from location and other fields
        location_str = str(event.get("location", ""))
        address = str(event.get("address", ""))
        venue_name = str(venue_field) if venue_field else ""
        
        # Extract area from location string (e.g., "Event Venue in Dubai Marina" -> "Dubai Marina")
        area = None
        if "in " in location_str:
            area = location_str.split("in ")[-1].strip()
        elif venue_name:
            area = venue_name
        
        if venue_name or location_str or area:
            venue_info = {
                "name": venue_name or "Event Venue",
                "area": area,
                "address": address or location_str,
                "amenities": {}
            }
    
    # Extract price information - check the actual pricing structure in MongoDB
    pricing_data = event.get("pricing", {})
    price_data = event.get("price_data", {})
    price_field = event.get("price", "")
    
    # Parse price from different possible formats
    price_min = 0
    price_max = None
    
    # First, check the 'pricing' field (this is where the actual data is)
    if isinstance(pricing_data, dict):
        price_min = pricing_data.get("base_price", 0) or 0
        price_max = pricing_data.get("max_price") or pricing_data.get("maxPrice")
        if price_min and price_min > 0:
            pass
    
    # Fallback to price_data structure
    elif isinstance(price_data, dict):
        price_min = price_data.get("min", 0) or price_data.get("price_min", 0)
        price_max = price_data.get("max") or price_data.get("price_max")
    
    # Fallback to price field
    elif price_field:
        # Try to parse price from string like "Free", "100 AED", "50-200 AED"
        if "free" in str(price_field).lower():
            price_min = 0
            price_max = 0
        else:
            # Extract numbers from price string
            import re
            numbers = re.findall(r'\d+', str(price_field))
            if numbers:
                price_min = float(numbers[0])
                if len(numbers) > 1:
                    price_max = float(numbers[1])
    
    price_info = {
        "min": price_min,
        "max": price_max,
        "currency": event.get("currency", "AED")
    }
    
    # Determine if event is family-friendly based on tags and content
    tags = event.get("tags", [])
    # Ensure tags is a list
    if not isinstance(tags, list):
        tags = []
    is_family_friendly = True  # Default to True
    
    # Check if tags indicate family content
    family_tags = ["family", "kids", "children", "educational", "cultural", "outdoor"]
    non_family_tags = ["nightclub", "bar", "adults only", "18+", "21+"]
    
    if any(tag.lower() in [t.lower() for t in non_family_tags] for tag in tags):
        is_family_friendly = False
    elif any(tag.lower() in [t.lower() for t in family_tags] for tag in tags):
        is_family_friendly = True
    
    # Extract category from available fields  
    category = event.get("category", "General")
    
    # Ensure we have a valid category
    if not category or category in ["", "null", None]:
        category = "General"
    
    # Generate a basic family score based on tags and price
    family_score = 50  # Default score
    if is_family_friendly:
        family_score += 30
    if price_min == 0:  # Free events are more family-friendly
        family_score += 20
    if price_min > 500:  # Expensive events are less family-friendly
        family_score -= 20
    family_score = max(0, min(100, family_score))
    
    # Extract image URLs
    image_urls = []
    
    # Priority order: images.ai_generated > ai_image_url > image_url > image_urls
    if event.get("images") and isinstance(event["images"], dict) and event["images"].get("ai_generated"):
        image_urls = [event["images"]["ai_generated"]]
    elif event.get("ai_image_url"):
        image_urls = [event["ai_image_url"]]
    elif event.get("image_url"):
        image_urls = [event["image_url"]]
    elif event.get("image_urls"):
        image_urls = event["image_urls"]
    
    # Extract source name
    source_name = None
    source = event.get("source", {})
    if isinstance(source, dict):
        source_name = source.get("name")
    elif isinstance(source, str):
        source_name = source
    
    # Ensure dates are properly formatted
    start_date = event["start_date"]
    end_date = event.get("end_date")
    
    # Convert string dates to proper ISO format if needed
    if isinstance(start_date, str):
        try:
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError:
            # If parsing fails, try to parse without timezone info
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass  # Use as-is if parsing fails
    
    if isinstance(end_date, str):
        try:
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass  # Use as-is if parsing fails

    return EventResponse(
        id=str(event["_id"]),
        title=event["title"],
        description=event.get("description"),
        start_date=start_date,
        end_date=end_date,
        venue=venue_info,
        price=price_info,
        family_score=family_score,
        age_range=f"{event.get('age_min', 0)}-{event.get('age_max', 99)}",
        tags=tags,
        category=category,
        is_saved=is_saved,
        image_urls=image_urls,
        booking_url=event.get("event_url"),  # Use event_url as booking_url
        is_family_friendly=is_family_friendly,
        duration_hours=event.get("duration_hours"),
        source_name=source_name,
        
        # Enhanced fields from Perplexity extraction
        event_url=event.get("event_url"),
        source_url=event.get("source_url"),
        social_media=event.get("social_media"),
        quality_metrics=event.get("quality_metrics"),
        ticket_links=event.get("ticket_links", []),
        contact_info=event.get("contact_info"),
        target_audience=event.get("target_audience", []),
        age_restrictions=event.get("age_restrictions"),
        dress_code=event.get("dress_code"),
        recurring=event.get("recurring"),
        venue_type=event.get("venue_type"),
        metro_accessible=event.get("metro_accessible"),
        special_needs_friendly=event.get("special_needs_friendly"),
        language_requirements=event.get("language_requirements"),
        alcohol_served=event.get("alcohol_served"),
        transportation_notes=event.get("transportation_notes"),
        primary_category=event.get("primary_category"),
        secondary_categories=event.get("secondary_categories", []),
        event_type=event.get("event_type"),
        indoor_outdoor=event.get("indoor_outdoor"),
        special_occasion=event.get("special_occasion")
    )


async def _get_filter_options(db: AsyncIOMotorDatabase) -> dict[str, list[str]]:
    """Get available filter options for the frontend."""
    # Get unique categories from both category field and tags
    categories = await db.events.distinct("category", {"status": "active"})
    tags = await db.events.distinct("tags", {"status": "active"})
    # Combine and flatten categories and tags
    all_categories = set()
    if categories:
        all_categories.update([cat for cat in categories if cat])
    if tags:
        # Flatten the tags list since it's an array field
        for tag_list in tags:
            if isinstance(tag_list, list):
                all_categories.update(tag_list)
            elif tag_list:
                all_categories.add(tag_list)
    # Extract areas from location strings
    locations = await db.events.distinct(
        "location", {"status": "active", "location": {"$ne": None}}
    )
    areas = set()
    for location in locations:
        if "in " in str(location):
            area = str(location).split("in ")[-1].strip()
            areas.add(area)
    # Define price ranges
    price_ranges = [
        {"label": "Free", "min": 0, "max": 0},
        {"label": "Budget (1-100 AED)", "min": 1, "max": 100},
        {"label": "Moderate (101-500 AED)", "min": 101, "max": 500},
        {"label": "Premium (500+ AED)", "min": 501, "max": None},
    ]
    
    # Define age groups
    age_groups = ["child", "teen", "adult", "family"]
    return {
        "categories": sorted([cat for cat in all_categories if cat]),
        "areas": sorted([area for area in areas if area]),
        "price_ranges": price_ranges,
        "age_groups": age_groups,
    }


@router.post("/deduplicate")
async def deduplicate_events(
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Run automatic deduplication on the events database.
    This endpoint is designed to be called by cron jobs.
    """
    try:
        # Initialize deduplicator
        deduplicator = EventDeduplicator(db)
        
        # Get initial stats
        initial_stats = await deduplicator.get_duplicate_statistics()
        total_events = initial_stats.get('total_events', 0)
        estimated_duplicates = initial_stats.get('estimated_duplicates', 0)
        
        if estimated_duplicates == 0:
            return {
                "status": "success",
                "message": "No duplicates found - database is clean!",
                "stats": {
                    "total_events": total_events,
                    "duplicates_removed": 0,
                    "duplicates_remaining": 0
                }
            }
        
        # Find and remove duplicates using automated detection
        potential_duplicates = await deduplicator.find_potential_duplicates(limit=50)
        removed_count = 0
        
        for duplicate_info in potential_duplicates:
            try:
                similarity_score = duplicate_info.get('similarity_score', 0)
                if similarity_score >= 0.85:  # Conservative 85% threshold for automated daily runs
                    duplicate_id = duplicate_info.get('duplicate_id')
                    if duplicate_id:
                        await db.events.delete_one({"_id": duplicate_id})
                        removed_count += 1
            except Exception as e:
                print(f"Error removing duplicate: {e}")
                continue
        
        # Get final stats
        final_stats = await deduplicator.get_duplicate_statistics()
        final_total = final_stats.get('total_events', 0)
        remaining_duplicates = final_stats.get('estimated_duplicates', 0)
        
        return {
            "status": "success",
            "message": f"Deduplication completed successfully",
            "stats": {
                "initial_events": total_events,
                "final_events": final_total,
                "duplicates_removed": removed_count,
                "duplicates_remaining": remaining_duplicates
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during deduplication: {str(e)}"
        )