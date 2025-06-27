from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional
from datetime import datetime, timedelta
from pymongo import MongoClient, DESCENDING, ASCENDING
from bson import ObjectId
import os
import logging
from dotenv import load_dotenv

from models.advice_models import (
    EventAdviceModel, 
    EventAdviceStatsModel,
    AdviceFilterModel,
    CreateAdviceModel,
    AdviceInteractionModel,
    AdviceCategory,
    AdviceType
)
from utils.auth_dependencies import get_current_verified_user
from models.user_models import UserModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

router = APIRouter(prefix="/api/advice", tags=["Event Advice"])

# MongoDB connection using centralized config
from config import settings

try:
    client = MongoClient(settings.mongodb_url)
    db = client[settings.mongodb_database]
    advice_collection = db.event_advice
    events_collection = db.events
    users_collection = db.users
    logger.info("✅ MongoDB connection established for advice service")
except Exception as e:
    logger.error(f"❌ MongoDB connection error: {e}")
    advice_collection = None


@router.get("/event/{event_id}", response_model=List[EventAdviceModel])
async def get_event_advice(
    event_id: str,
    category: Optional[AdviceCategory] = None,
    advice_type: Optional[AdviceType] = None,
    verified_only: bool = False,
    featured_only: bool = False,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("helpfulness_rating", description="helpfulness_rating, created_at"),
    sort_order: str = Query("desc", description="asc or desc")
):
    """Get advice for a specific event with advanced filtering and sorting"""
    if advice_collection is None:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # Validate ObjectId format for event_id
        try:
            ObjectId(event_id)
        except Exception:
            logger.error(f"Invalid event ID format: {event_id}")
            raise HTTPException(status_code=400, detail="Invalid event ID format")
        
        # Build query
        query = {"event_id": event_id}
        
        if category:
            query["category"] = category.value
        
        if advice_type:
            query["advice_type"] = advice_type.value
        
        if verified_only:
            query["is_verified"] = True
        
        if featured_only:
            query["is_featured"] = True
        
        # Build sort
        sort_direction = DESCENDING if sort_order == "desc" else ASCENDING
        sort_field = sort_by
        
        # Execute query with optimized indexes
        logger.info(f"Executing query: {query} with sort: {sort_field} {sort_order}")
        cursor = advice_collection.find(query).sort(sort_field, sort_direction).skip(offset).limit(limit)
        advice_list = []
        
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            advice_list.append(EventAdviceModel(**doc))
        
        logger.info(f"Retrieved {len(advice_list)} advice entries for event {event_id}")
        return advice_list
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching advice for event {event_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching advice: {str(e)}")


@router.post("/", response_model=EventAdviceModel)
async def create_advice_direct(
    advice_data: CreateAdviceModel,
    current_user: UserModel = Depends(get_current_verified_user)
):
    """Create new advice for an event (direct endpoint for frontend compatibility)"""
    return await create_advice_impl(advice_data, current_user)


@router.post("/create", response_model=EventAdviceModel)
async def create_advice(
    advice_data: CreateAdviceModel,
    current_user: UserModel = Depends(get_current_verified_user)
):
    """Create new advice for an event (legacy endpoint)"""
    return await create_advice_impl(advice_data, current_user)


async def create_advice_impl(
    advice_data: CreateAdviceModel,
    current_user: UserModel
):
    if advice_collection is None:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # Validate event ID format
        try:
            ObjectId(advice_data.event_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid event ID format")
        
        # Verify event exists
        event = events_collection.find_one({"_id": ObjectId(advice_data.event_id)})
        if not event:
            logger.warning(f"Attempt to create advice for non-existent event: {advice_data.event_id}")
            raise HTTPException(status_code=404, detail="Event not found")
        
        # Check if user already provided advice for this event
        existing_advice = advice_collection.find_one({
            "event_id": advice_data.event_id,
            "user_id": str(current_user.id)
        })
        
        if existing_advice:
            logger.warning(f"User {current_user.id} attempted to create duplicate advice for event {advice_data.event_id}")
            raise HTTPException(
                status_code=400, 
                detail="You have already provided advice for this event. You can update your existing advice instead."
            )
        
        # Create advice document
        advice_doc = {
            "event_id": advice_data.event_id,
            "user_id": str(current_user.id),
            "user_name": current_user.name or current_user.email.split('@')[0],
            "user_avatar": getattr(current_user, 'avatar_url', None),
            "title": advice_data.title,
            "content": advice_data.content,
            "category": advice_data.category.value,
            "advice_type": advice_data.advice_type.value,
            "experience_date": advice_data.experience_date,
            "venue_familiarity": advice_data.venue_familiarity,
            "similar_events_attended": advice_data.similar_events_attended,
            "helpfulness_rating": 0.0,
            "helpfulness_votes": 0,
            "is_verified": False,
            "is_featured": False,
            "helpful_users": [],
            "reported_by": [],
            "tags": advice_data.tags,
            "language": advice_data.language,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = advice_collection.insert_one(advice_doc)
        advice_doc["_id"] = str(result.inserted_id)
        
        logger.info(f"Created new advice {result.inserted_id} for event {advice_data.event_id} by user {current_user.id}")
        return EventAdviceModel(**advice_doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating advice: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating advice: {str(e)}")


@router.put("/update/{advice_id}", response_model=EventAdviceModel)
async def update_advice(
    advice_id: str,
    advice_data: CreateAdviceModel,
    current_user: UserModel = Depends(get_current_verified_user)
):
    """Update existing advice with ownership validation"""
    if advice_collection is None:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # Validate ObjectId format
        try:
            ObjectId(advice_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid advice ID format")
        
        # Find existing advice
        existing_advice = advice_collection.find_one({"_id": ObjectId(advice_id)})
        if not existing_advice:
            logger.warning(f"Attempt to update non-existent advice: {advice_id}")
            raise HTTPException(status_code=404, detail="Advice not found")
        
        # Check ownership
        if existing_advice["user_id"] != str(current_user.id):
            logger.warning(f"User {current_user.id} attempted to update advice {advice_id} owned by {existing_advice['user_id']}")
            raise HTTPException(status_code=403, detail="You can only update your own advice")
        
        # Update document
        update_data = {
            "title": advice_data.title,
            "content": advice_data.content,
            "category": advice_data.category.value,
            "advice_type": advice_data.advice_type.value,
            "experience_date": advice_data.experience_date,
            "venue_familiarity": advice_data.venue_familiarity,
            "similar_events_attended": advice_data.similar_events_attended,
            "tags": advice_data.tags,
            "language": advice_data.language,
            "updated_at": datetime.utcnow()
        }
        
        advice_collection.update_one(
            {"_id": ObjectId(advice_id)},
            {"$set": update_data}
        )
        
        # Return updated advice
        updated_advice = advice_collection.find_one({"_id": ObjectId(advice_id)})
        updated_advice["_id"] = str(updated_advice["_id"])
        
        logger.info(f"Updated advice {advice_id} by user {current_user.id}")
        return EventAdviceModel(**updated_advice)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating advice {advice_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating advice: {str(e)}")


@router.post("/interact/{advice_id}")
async def interact_with_advice(
    advice_id: str,
    interaction_type: str,
    reason: Optional[str] = None,
    current_user: UserModel = Depends(get_current_verified_user)
):
    """Enhanced helpful functionality with better rating calculation and duplicate prevention"""
    if advice_collection is None:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    if interaction_type not in ["helpful", "not_helpful", "report"]:
        raise HTTPException(status_code=400, detail="Invalid interaction type. Must be 'helpful', 'not_helpful', or 'report'")
    
    try:
        # Validate ObjectId format
        try:
            ObjectId(advice_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid advice ID format")
        
        # Find advice
        advice = advice_collection.find_one({"_id": ObjectId(advice_id)})
        if not advice:
            logger.warning(f"Attempt to interact with non-existent advice: {advice_id}")
            raise HTTPException(status_code=404, detail="Advice not found")
        
        user_id = str(current_user.id)
        
        # Prevent users from rating their own advice
        if advice["user_id"] == user_id:
            logger.warning(f"User {user_id} attempted to rate their own advice {advice_id}")
            raise HTTPException(status_code=400, detail="You cannot rate your own advice")
        
        if interaction_type == "helpful":
            # Check if user already marked as helpful
            if user_id in advice.get("helpful_users", []):
                logger.info(f"User {user_id} already marked advice {advice_id} as helpful")
                return {"message": "You have already marked this advice as helpful", "already_voted": True}
            
            # Add user to helpful_users and increment votes
            result = advice_collection.update_one(
                {"_id": ObjectId(advice_id)},
                {
                    "$addToSet": {"helpful_users": user_id},
                    "$inc": {"helpfulness_votes": 1}
                }
            )
            
            if result.modified_count > 0:
                # Recalculate helpfulness rating (improved algorithm)
                updated_advice = advice_collection.find_one({"_id": ObjectId(advice_id)})
                votes = updated_advice["helpfulness_votes"]
                # Use a more sophisticated rating calculation
                helpfulness_rating = min(5.0, (votes * 0.2) + (votes / (votes + 5)) * 4.8)
                
                advice_collection.update_one(
                    {"_id": ObjectId(advice_id)},
                    {"$set": {"helpfulness_rating": round(helpfulness_rating, 2)}}
                )
                
                logger.info(f"User {user_id} marked advice {advice_id} as helpful. New rating: {helpfulness_rating:.2f}")
        
        elif interaction_type == "not_helpful":
            # Remove user from helpful_users if there and decrement votes
            if user_id in advice.get("helpful_users", []):
                result = advice_collection.update_one(
                    {"_id": ObjectId(advice_id)},
                    {
                        "$pull": {"helpful_users": user_id},
                        "$inc": {"helpfulness_votes": -1}
                    }
                )
                
                if result.modified_count > 0:
                    # Recalculate helpfulness rating
                    updated_advice = advice_collection.find_one({"_id": ObjectId(advice_id)})
                    votes = max(0, updated_advice["helpfulness_votes"])
                    helpfulness_rating = min(5.0, (votes * 0.2) + (votes / (votes + 5)) * 4.8) if votes > 0 else 0.0
                    
                    advice_collection.update_one(
                        {"_id": ObjectId(advice_id)},
                        {"$set": {"helpfulness_rating": round(helpfulness_rating, 2)}}
                    )
                    
                    logger.info(f"User {user_id} removed helpful vote from advice {advice_id}. New rating: {helpfulness_rating:.2f}")
            else:
                logger.info(f"User {user_id} tried to remove helpful vote from advice {advice_id} but hadn't voted")
                return {"message": "You haven't marked this advice as helpful yet", "already_voted": False}
        
        elif interaction_type == "report":
            # Check if user already reported
            if user_id in advice.get("reported_by", []):
                logger.info(f"User {user_id} already reported advice {advice_id}")
                return {"message": "You have already reported this advice", "already_reported": True}
            
            # Add user to reported_by
            advice_collection.update_one(
                {"_id": ObjectId(advice_id)},
                {"$addToSet": {"reported_by": user_id}}
            )
            
            logger.warning(f"User {user_id} reported advice {advice_id}. Reason: {reason}")
        
        return {"message": f"Advice {interaction_type} recorded successfully", "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording interaction {interaction_type} for advice {advice_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error recording interaction: {str(e)}")


@router.get("/stats/{event_id}", response_model=EventAdviceStatsModel)
async def get_advice_stats(event_id: str):
    """Get comprehensive advice statistics for an event"""
    if advice_collection is None:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # Validate ObjectId format
        try:
            ObjectId(event_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid event ID format")
        
        # Aggregate stats using optimized pipeline
        pipeline = [
            {"$match": {"event_id": event_id}},
            {
                "$group": {
                    "_id": None,
                    "total_advice": {"$sum": 1},
                    "average_helpfulness": {"$avg": "$helpfulness_rating"},
                    "verified_count": {"$sum": {"$cond": ["$is_verified", 1, 0]}},
                    "featured_count": {"$sum": {"$cond": ["$is_featured", 1, 0]}},
                    "categories": {"$push": "$category"},
                    "advice_types": {"$push": "$advice_type"},
                    "all_tags": {"$push": "$tags"}
                }
            }
        ]
        
        result = list(advice_collection.aggregate(pipeline))
        
        if not result:
            logger.info(f"No advice found for event {event_id}")
            return EventAdviceStatsModel(
                event_id=event_id,
                total_advice=0,
                average_helpfulness=0.0,
                advice_by_category={},
                advice_by_type={},
                verified_advice_count=0,
                featured_advice_count=0,
                recent_advice_count=0,
                top_tags=[]
            )
        
        stats = result[0]
        
        # Count categories
        advice_by_category = {}
        for category in stats.get("categories", []):
            advice_by_category[category] = advice_by_category.get(category, 0) + 1
        
        # Count advice types
        advice_by_type = {}
        for advice_type in stats.get("advice_types", []):
            advice_by_type[advice_type] = advice_by_type.get(advice_type, 0) + 1
        
        # Count recent advice (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_count = advice_collection.count_documents({
            "event_id": event_id,
            "created_at": {"$gte": thirty_days_ago}
        })
        
        # Get top tags
        all_tags = []
        for tag_list in stats.get("all_tags", []):
            all_tags.extend(tag_list)
        
        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        top_tags = sorted(tag_counts.keys(), key=lambda x: tag_counts[x], reverse=True)[:5]
        
        logger.info(f"Generated stats for event {event_id}: {stats.get('total_advice', 0)} advice entries")
        
        return EventAdviceStatsModel(
            event_id=event_id,
            total_advice=stats.get("total_advice", 0),
            average_helpfulness=round(stats.get("average_helpfulness", 0.0), 2),
            advice_by_category=advice_by_category,
            advice_by_type=advice_by_type,
            verified_advice_count=stats.get("verified_count", 0),
            featured_advice_count=stats.get("featured_count", 0),
            recent_advice_count=recent_count,
            top_tags=top_tags
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stats for event {event_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


@router.delete("/delete/{advice_id}")
async def delete_advice(
    advice_id: str,
    current_user: UserModel = Depends(get_current_verified_user)
):
    """Delete advice with proper authorization"""
    if advice_collection is None:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # Validate ObjectId format
        try:
            ObjectId(advice_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid advice ID format")
        
        # Find advice
        advice = advice_collection.find_one({"_id": ObjectId(advice_id)})
        if not advice:
            logger.warning(f"Attempt to delete non-existent advice: {advice_id}")
            raise HTTPException(status_code=404, detail="Advice not found")
        
        # Check ownership or admin status
        is_admin = getattr(current_user, 'is_admin', False)
        if advice["user_id"] != str(current_user.id) and not is_admin:
            logger.warning(f"User {current_user.id} attempted to delete advice {advice_id} owned by {advice['user_id']}")
            raise HTTPException(status_code=403, detail="You can only delete your own advice")
        
        # Delete advice
        result = advice_collection.delete_one({"_id": ObjectId(advice_id)})
        
        if result.deleted_count > 0:
            logger.info(f"Deleted advice {advice_id} by user {current_user.id}")
            return {"message": "Advice deleted successfully", "success": True}
        else:
            logger.error(f"Failed to delete advice {advice_id}")
            raise HTTPException(status_code=500, detail="Failed to delete advice")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting advice {advice_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting advice: {str(e)}")


@router.get("/categories", response_model=List[str])
async def get_advice_categories():
    """Get all available advice categories for frontend dropdowns"""
    logger.info("Retrieved advice categories")
    return [category.value for category in AdviceCategory]


@router.get("/types", response_model=List[str])
async def get_advice_types():
    """Get all available advice types for frontend dropdowns"""
    logger.info("Retrieved advice types")
    return [advice_type.value for advice_type in AdviceType]


@router.get("/user/{user_id}", response_model=List[EventAdviceModel])
async def get_user_advice(
    user_id: str,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: UserModel = Depends(get_current_verified_user)
):
    """Get advice provided by a specific user with proper authorization"""
    if advice_collection is None:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # Validate ObjectId format
        try:
            ObjectId(user_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        # Only allow users to see their own advice or admins to see all
        is_admin = getattr(current_user, 'is_admin', False)
        if user_id != str(current_user.id) and not is_admin:
            logger.warning(f"User {current_user.id} attempted to access advice for user {user_id}")
            return []  # Return empty for security
        
        cursor = advice_collection.find(
            {"user_id": user_id}
        ).sort("created_at", DESCENDING).skip(offset).limit(limit)
        
        advice_list = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            advice_list.append(EventAdviceModel(**doc))
        
        logger.info(f"Retrieved {len(advice_list)} advice entries for user {user_id}")
        return advice_list
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user advice for {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching user advice: {str(e)}")


@router.get("/check-user-interaction/{advice_id}")
async def check_user_interaction(
    advice_id: str,
    current_user: UserModel = Depends(get_current_verified_user)
):
    """Check if current user has already interacted with specific advice"""
    if advice_collection is None:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        # Validate ObjectId format
        try:
            ObjectId(advice_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid advice ID format")
        
        # Find advice
        advice = advice_collection.find_one({"_id": ObjectId(advice_id)})
        if not advice:
            raise HTTPException(status_code=404, detail="Advice not found")
        
        user_id = str(current_user.id)
        
        interaction_status = {
            "advice_id": advice_id,
            "user_id": user_id,
            "is_owner": advice.get("user_id") == user_id,
            "has_marked_helpful": user_id in advice.get("helpful_users", []),
            "has_reported": user_id in advice.get("reported_by", []),
            "current_rating": advice.get("helpfulness_rating", 0.0),
            "total_votes": advice.get("helpfulness_votes", 0)
        }
        
        logger.info(f"Checked interaction status for user {user_id} on advice {advice_id}")
        return interaction_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking user interaction for advice {advice_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking interaction: {str(e)}")


@router.get("/health")
async def advice_health_check():
    """Health check endpoint for advice service"""
    try:
        if advice_collection is None:
            return {
                "status": "unhealthy",
                "database": "disconnected",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Test database connection
        count = advice_collection.count_documents({})
        
        return {
            "status": "healthy",
            "database": "connected",
            "total_advice": count,
            "timestamp": datetime.utcnow().isoformat(),
            "features": {
                "create_advice": "enabled",
                "helpful_functionality": "enabled",
                "reporting": "enabled",
                "statistics": "enabled"
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        } 