#!/usr/bin/env python3
"""
Add a debug endpoint to help identify the 500 error
"""

debug_endpoint_code = '''

@router.post("/debug", response_model=dict)
async def debug_advice_creation(
    request: dict,
    current_user: UserModel = Depends(get_current_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """Debug endpoint to test advice creation components"""
    debug_info = {
        "status": "starting_debug",
        "timestamp": datetime.utcnow().isoformat(),
        "user_info": {},
        "database_info": {},
        "request_info": request
    }
    
    try:
        # Test user object
        debug_info["user_info"] = {
            "user_id": str(current_user.id),
            "email": current_user.email,
            "first_name": getattr(current_user, 'first_name', None),
            "is_email_verified": getattr(current_user, 'is_email_verified', None),
            "has_avatar": hasattr(current_user, 'avatar')
        }
        
        # Test database connections
        advice_collection = db.event_advice
        events_collection = db.events
        
        advice_count = await advice_collection.count_documents({})
        events_count = await events_collection.count_documents({})
        
        debug_info["database_info"] = {
            "advice_collection_count": advice_count,
            "events_collection_count": events_count,
            "database_name": db.name
        }
        
        # Test event ID validation if provided
        if "event_id" in request:
            try:
                ObjectId(request["event_id"])
                debug_info["event_id_validation"] = "valid"
                
                # Test if event exists
                event = await events_collection.find_one({"_id": ObjectId(request["event_id"])})
                debug_info["event_exists"] = event is not None
                if event:
                    debug_info["event_title"] = event.get("title", "No title")
            except Exception as e:
                debug_info["event_id_validation"] = f"invalid: {str(e)}"
        
        debug_info["status"] = "debug_completed_successfully"
        return debug_info
        
    except Exception as e:
        debug_info["status"] = "debug_failed"
        debug_info["error"] = str(e)
        import traceback
        debug_info["traceback"] = traceback.format_exc()
        return debug_info
'''

def add_debug_endpoint():
    """Add the debug endpoint to the advice router"""
    
    with open('routers/event_advice.py', 'r') as f:
        content = f.read()
    
    # Check if debug endpoint already exists
    if '@router.post("/debug"' in content:
        print("⚠️  Debug endpoint already exists")
        return True
    
    # Add the debug endpoint before the last function or at the end
    # Find a good insertion point (before the last router endpoint)
    insertion_point = content.rfind('@router.')
    if insertion_point == -1:
        # If no router found, add at the end
        insertion_point = len(content)
    else:
        # Add before the last router endpoint
        insertion_point = content.rfind('\n', 0, insertion_point)
        if insertion_point == -1:
            insertion_point = 0
    
    # Insert the debug endpoint
    new_content = content[:insertion_point] + debug_endpoint_code + '\n' + content[insertion_point:]
    
    with open('routers/event_advice.py', 'w') as f:
        f.write(new_content)
    
    print("✅ Debug endpoint added to advice router")
    return True

if __name__ == "__main__":
    import os
    os.chdir('/home/ubuntu/mydscvr-backend/Backend')
    if add_debug_endpoint():
        print("🔄 Restart the backend service to apply changes:")
        print("sudo systemctl restart mydscvr-backend")
        print("🧪 Test the debug endpoint with:")
        print('curl -X POST https://mydscvr.xyz/api/advice/debug -H "Authorization: Bearer YOUR_TOKEN" -H "Content-Type: application/json" -d \'{"event_id":"test"}\'')
    else:
        print("❌ Failed to add debug endpoint")