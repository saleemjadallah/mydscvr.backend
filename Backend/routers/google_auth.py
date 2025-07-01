from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse, Response
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import logging
from typing import Dict, Any
import json

from config import settings
from models.user_models import User
from utils.jwt_config import create_access_token, create_refresh_token
from database import get_mongodb

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/google", tags=["Google Authentication"])

# Google OAuth flow configuration
def get_google_oauth_flow():
    """Create and configure Google OAuth flow"""
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=['openid', 'email', 'profile'],
        redirect_uri=settings.google_redirect_uri
    )
    
    return flow

@router.get("/login")
async def google_login():
    """Initiate Google OAuth login flow"""
    try:
        flow = get_google_oauth_flow()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        logger.info(f"Redirecting to Google OAuth: {authorization_url}")
        return RedirectResponse(url=authorization_url)
        
    except Exception as e:
        logger.error(f"Error initiating Google OAuth: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initiate Google login")

@router.get("/callback")
async def google_callback(request: Request):
    """Handle Google OAuth callback"""
    try:
        # Get the full URL from the request
        callback_url = str(request.url)
        logger.info(f"Google callback received: {callback_url}")
        
        # Configure the OAuth flow
        flow = get_google_oauth_flow()
        
        # Exchange authorization code for tokens
        flow.fetch_token(authorization_response=callback_url)
        
        # Get user info from Google
        credentials = flow.credentials
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            GoogleRequest(),
            settings.google_client_id
        )
        
        logger.info(f"Google user info received: {id_info}")
        
        # Extract user information
        google_id = id_info.get('sub')
        email = id_info.get('email')
        name = id_info.get('name', '')
        
        if not google_id or not email:
            raise HTTPException(status_code=400, detail="Invalid Google user data")
        
        # Check if user exists or create new user
        db = await get_mongodb()
        user_collection = db.users
        
        # First check if user exists by Google ID
        existing_user = await user_collection.find_one({"google_id": google_id})
        
        if not existing_user:
            # Check if user exists by email (for account linking)
            existing_user = await user_collection.find_one({"email": email})
            
            if existing_user:
                # Link Google account to existing email account
                await user_collection.update_one(
                    {"_id": existing_user["_id"]},
                    {
                        "$set": {
                            "google_id": google_id,
                            "auth_provider": "both",  # User has both email and Google auth
                            "email_verified": True,  # Google emails are pre-verified
                            "is_email_verified": True  # Google emails are pre-verified
                        }
                    }
                )
                logger.info(f"Linked Google account to existing user: {email}")
            else:
                # Create new user
                from datetime import datetime, timezone
                current_time = datetime.now(timezone.utc).isoformat()
                
                new_user_data = {
                    "email": email,
                    "name": name,
                    "google_id": google_id,
                    "auth_provider": "google",
                    "email_verified": True,  # Google emails are pre-verified
                    "is_email_verified": True,  # Google emails are pre-verified
                    "is_active": True,
                    "created_at": current_time,
                    "updated_at": current_time,
                    "preferences": {
                        "newsletter_subscribed": False,
                        "push_notifications": True,
                        "email_notifications": True
                    }
                }
                
                result = await user_collection.insert_one(new_user_data)
                logger.info(f"Created new Google user: {email}")
                
                # Fetch the created user
                existing_user = await user_collection.find_one({"_id": result.inserted_id})
        
        # Convert MongoDB ObjectId to string for JWT
        user_id = str(existing_user["_id"])
        
        # Create JWT tokens
        access_token = create_access_token(data={"sub": user_id, "email": email})
        refresh_token = create_refresh_token(data={"sub": user_id})
        
        # Create frontend redirect URL with tokens
        frontend_url = "https://mydscvr.ai"
        redirect_url = f"{frontend_url}/#/auth-success?access_token={access_token}&refresh_token={refresh_token}"
        
        logger.info(f"Redirecting user to: {redirect_url}")
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        logger.error(f"Error in Google callback: {str(e)}")
        # Redirect to frontend with error
        error_url = "https://mydscvr.ai/#/auth-error"
        return RedirectResponse(url=error_url)

@router.options("/verify")
async def verify_options():
    """Handle OPTIONS request for /verify endpoint (CORS preflight)"""
    return Response(status_code=200)

@router.post("/verify")
async def verify_google_token(token_data: Dict[str, Any]):
    """Verify Google ID token (for mobile/web direct integration)"""
    try:
        id_token_str = token_data.get("id_token")
        if not id_token_str:
            raise HTTPException(status_code=400, detail="ID token required")
        
        # Verify the token
        id_info = id_token.verify_oauth2_token(
            id_token_str,
            GoogleRequest(),
            settings.google_client_id
        )
        
        google_id = id_info.get('sub')
        email = id_info.get('email')
        name = id_info.get('name', '')
        
        if not google_id or not email:
            raise HTTPException(status_code=400, detail="Invalid Google token")
        
        # Same user creation/lookup logic as callback
        db = await get_mongodb()
        user_collection = db.users
        existing_user = await user_collection.find_one({"google_id": google_id})
        
        if not existing_user:
            existing_user = await user_collection.find_one({"email": email})
            
            if existing_user:
                await user_collection.update_one(
                    {"_id": existing_user["_id"]},
                    {
                        "$set": {
                            "google_id": google_id,
                            "auth_provider": "both",
                            "email_verified": True,  # Google emails are pre-verified
                            "is_email_verified": True  # Google emails are pre-verified
                        }
                    }
                )
            else:
                from datetime import datetime, timezone
                current_time = datetime.now(timezone.utc).isoformat()
                
                new_user_data = {
                    "email": email,
                    "name": name,
                    "google_id": google_id,
                    "auth_provider": "google",
                    "email_verified": True,  # Google emails are pre-verified
                    "is_email_verified": True,  # Google emails are pre-verified
                    "is_active": True,
                    "created_at": current_time,
                    "updated_at": current_time,
                    "preferences": {
                        "newsletter_subscribed": False,
                        "push_notifications": True,
                        "email_notifications": True
                    }
                }
                
                result = await user_collection.insert_one(new_user_data)
                existing_user = await user_collection.find_one({"_id": result.inserted_id})
        
        user_id = str(existing_user["_id"])
        access_token = create_access_token(data={"sub": user_id, "email": email})
        refresh_token = create_refresh_token(data={"sub": user_id})
        
        # Parse name into first and last name
        name_parts = name.split(' ', 1) if name else ['', '']
        first_name = name_parts[0] if len(name_parts) > 0 else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "phone_number": existing_user.get("phone_number"),
                "avatar": existing_user.get("avatar"),
                "date_of_birth": existing_user.get("date_of_birth"),
                "gender": existing_user.get("gender"),
                "interests": existing_user.get("interests", []),
                "preferences": existing_user.get("preferences", {
                    "newsletter_subscribed": False,
                    "push_notifications": True,
                    "email_notifications": True
                }),
                "is_email_verified": existing_user.get("is_email_verified", True),
                "is_phone_verified": existing_user.get("phone_verified", False),
                "created_at": existing_user.get("created_at", "2024-01-01T00:00:00Z"),
                "updated_at": existing_user.get("updated_at", "2024-01-01T00:00:00Z"),
                "onboardingCompleted": existing_user.get("onboarding_completed", False),
                "auth_provider": existing_user.get("auth_provider", "google")
            }
        }
        
    except Exception as e:
        logger.error(f"Error verifying Google token: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid Google token")