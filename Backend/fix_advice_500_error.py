#!/usr/bin/env python3
"""
Script to add better error handling to the advice creation endpoint
This will help identify and fix the 500 error
"""

import re

def fix_advice_endpoint():
    """Add better error handling to the advice creation endpoint"""
    
    # Read the current file
    with open('routers/event_advice.py', 'r') as f:
        content = f.read()
    
    # Enhanced error handling for the create_advice_direct function
    enhanced_function = '''@router.post("/", response_model=EventAdviceModel)
async def create_advice_direct(
    advice_data: CreateAdviceModel,
    current_user: UserModel = Depends(get_current_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """Create new advice for an event (direct endpoint for frontend compatibility)"""
    try:
        logger.info(f"📝 Starting advice creation for user {getattr(current_user, 'id', 'unknown')}")
        logger.info(f"📝 Advice data: {advice_data.dict()}")
        
        advice_collection = db.event_advice
        events_collection = db.events
        
        # Validate event ID format
        try:
            event_object_id = ObjectId(advice_data.event_id)
            logger.info(f"📝 Event ID validation successful: {advice_data.event_id}")
        except Exception as e:
            logger.error(f"📝 Invalid event ID format: {advice_data.event_id}, error: {e}")
            raise HTTPException(status_code=400, detail="Invalid event ID format")
        
        # Verify event exists
        logger.info(f"📝 Checking if event exists: {advice_data.event_id}")
        event = await events_collection.find_one({"_id": event_object_id})
        if not event:
            logger.warning(f"📝 Event not found: {advice_data.event_id}")
            raise HTTPException(status_code=404, detail="Event not found")
        
        logger.info(f"📝 Event found: {event.get('title', 'No title')}")
        
        # Check user object
        try:
            user_id = str(current_user.id)
            user_name = current_user.first_name or current_user.email.split('@')[0]
            user_avatar = getattr(current_user, 'avatar', None)
            logger.info(f"📝 User data extracted - ID: {user_id}, Name: {user_name}")
        except Exception as e:
            logger.error(f"📝 Error extracting user data: {e}")
            raise HTTPException(status_code=500, detail=f"User data error: {str(e)}")
        
        # Check if user already provided advice for this event
        logger.info(f"📝 Checking for existing advice from user {user_id} for event {advice_data.event_id}")
        existing_advice = await advice_collection.find_one({
            "event_id": advice_data.event_id,
            "user_id": user_id
        })
        
        if existing_advice:
            logger.warning(f"📝 Duplicate advice attempt - User {user_id} for event {advice_data.event_id}")
            raise HTTPException(
                status_code=400, 
                detail="You have already provided advice for this event. You can update your existing advice instead."
            )
        
        # Create advice document
        logger.info(f"📝 Creating advice document...")
        advice_doc = {
            "event_id": advice_data.event_id,
            "user_id": user_id,
            "user_name": user_name,
            "user_avatar": user_avatar,
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
        
        logger.info(f"📝 Inserting advice document into database...")
        result = await advice_collection.insert_one(advice_doc)
        advice_doc["_id"] = str(result.inserted_id)
        
        logger.info(f"📝 Advice created successfully with ID: {result.inserted_id}")
        return EventAdviceModel(**advice_doc)
        
    except HTTPException:
        # Re-raise HTTP exceptions (they're handled properly)
        raise
    except Exception as e:
        # Log unexpected errors with full traceback
        import traceback
        logger.error(f"📝 Unexpected error creating advice: {str(e)}")
        logger.error(f"📝 Traceback: {traceback.format_exc()}")
        
        # Return a proper 500 error with details for debugging
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )'''
    
    # Find and replace the function
    # Pattern to match the entire function
    pattern = r'@router\.post\("/", response_model=EventAdviceModel\)\s*async def create_advice_direct\(.*?\n(?:    .*\n)*?        raise HTTPException\(status_code=500.*?\n(?:    .*\n)*?'
    
    # Find the start and end of the function more precisely
    start_marker = '@router.post("/", response_model=EventAdviceModel)'
    start_pos = content.find(start_marker)
    
    if start_pos == -1:
        print("❌ Could not find the create_advice_direct function")
        return False
    
    # Find the end of the function (next @router or end of file)
    next_router_pos = content.find('\n@router.', start_pos + 1)
    if next_router_pos == -1:
        # If no next router, find the next function definition
        next_func_pos = content.find('\n\ndef ', start_pos + 1)
        if next_func_pos == -1:
            next_func_pos = len(content)
        end_pos = next_func_pos
    else:
        end_pos = next_router_pos
    
    # Replace the function
    new_content = content[:start_pos] + enhanced_function + '\n\n' + content[end_pos:]
    
    # Write the updated file
    with open('routers/event_advice.py', 'w') as f:
        f.write(new_content)
    
    print("✅ Enhanced error handling added to advice creation endpoint")
    return True

if __name__ == "__main__":
    import os
    os.chdir('/home/ubuntu/mydscvr-backend/Backend')
    if fix_advice_endpoint():
        print("🔄 Restart the backend service to apply changes:")
        print("sudo systemctl restart mydscvr-backend")
    else:
        print("❌ Failed to apply fixes")