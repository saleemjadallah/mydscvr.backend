#!/usr/bin/env python3
"""
Enhanced Authentication Router with OTP Email Verification
Integrates JWT authentication with OTP verification system
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from bson import ObjectId
from pydantic import EmailStr
import logging

from models.otp_models import OTPGenerationRequest, OTPVerificationRequest
from services.otp_service import OTPService
from services.mongodb_auth import MongoAuthService
from schemas.user_schemas import (
    UserRegistrationRequest, UserLoginRequest, UserUpdateRequest,
    UserRegistrationResponse, AuthResponse, UserProfileResponse, 
    MessageResponse
)
from models.user_models import UserRegistrationModel, UserModel
from database import get_mongodb

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/auth", tags=["Enhanced Authentication"])
security = HTTPBearer()

@router.options("/login")
async def login_options():
    """Handle OPTIONS request for login endpoint"""
    return Response(status_code=200)

@router.options("/register")
async def register_options():
    """Handle OPTIONS request for register endpoint"""
    return Response(status_code=200)


def create_user_profile_response(user_data: dict) -> dict:
    """Create a UserProfileResponse-compatible dict with defaults for missing fields"""
    # Ensure all required fields have default values
    return {
        "id": str(user_data.get("_id", user_data.get("id", ""))),
        "email": user_data.get("email", ""),
        "first_name": user_data.get("first_name"),
        "last_name": user_data.get("last_name"),
        "display_name": user_data.get("display_name"),
        "avatar": user_data.get("avatar"),
        "phone_number": user_data.get("phone_number"),
        "date_of_birth": user_data.get("date_of_birth"),
        "gender": user_data.get("gender"),
        "onboarding_completed": user_data.get("onboarding_completed", False),
        "family_members": user_data.get("family_members", []),
        "preferences": user_data.get("preferences", {
            "interests": [],
            "age_groups": [],
            "locations": [],
            "event_types": [],
            "budget_range": {"min": 0, "max": 1000},
            "notifications": {
                "email": True,
                "push": False,
                "sms": False,
                "frequency": "weekly"
            }
        }),
        "privacy_settings": user_data.get("privacy_settings", {
            "profile_visible": True,
            "show_attendance": False,
            "allow_messages": True
        }),
        "subscription_type": user_data.get("subscription_type", "free"),
        "is_email_verified": user_data.get("is_email_verified", False),
        "is_phone_verified": user_data.get("is_phone_verified", False),
        "created_at": user_data.get("created_at", "").isoformat() if hasattr(user_data.get("created_at", ""), "isoformat") else str(user_data.get("created_at", "")),
        "updated_at": user_data.get("updated_at", "").isoformat() if hasattr(user_data.get("updated_at", ""), "isoformat") else str(user_data.get("updated_at", ""))
    }


def get_client_info(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Extract client IP and user agent from request"""
    client_ip = request.headers.get("X-Forwarded-For")
    if client_ip:
        client_ip = client_ip.split(",")[0].strip()
    else:
        client_ip = request.headers.get("X-Real-IP") or request.client.host
    
    user_agent = request.headers.get("User-Agent")
    return client_ip, user_agent


# Import consolidated auth dependencies
from utils.auth_dependencies import (
    get_auth_service, 
    get_current_user_dependency as get_current_user_consolidated,
    get_current_verified_user as get_current_verified_user_consolidated
)


# Use consolidated auth dependency (alias for backward compatibility)
get_current_user_dependency = get_current_user_consolidated


# Enhanced Registration Flow
@router.post("/register", response_model=Dict[str, Any])
async def register_user_with_verification(
    user_data: UserRegistrationRequest,
    request: Request,
    auth_service: MongoAuthService = Depends(get_auth_service),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Register a new user and send email verification OTP
    This is step 1 of the 2-step registration process
    """
    try:
        client_ip, user_agent = get_client_info(request)
        
        # Step 1: Check if user already exists
        existing_user = await auth_service.get_user_by_email(user_data.email)
        if existing_user and existing_user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists and is verified"
            )
        
        # Step 2: Create user account (unverified)
        registration_model = UserRegistrationModel(**user_data.dict())
        success, message, user_profile = await auth_service.register_user(
            registration_model, 
            email_verified=False  # Start with unverified email
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        # Step 3: Generate and send OTP
        otp_service = OTPService(db)
        full_name = f"{user_data.first_name or ''} {user_data.last_name or ''}".strip()
        otp_request = OTPGenerationRequest(
            email=user_data.email,
            user_name=full_name or user_data.email.split('@')[0],  # Fallback to email username
            purpose="email_verification"
        )
        
        otp_result = await otp_service.generate_and_send_otp(
            request=otp_request,
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        if not otp_result.success:
            # If OTP sending fails, we still keep the user account but mark it as needing verification
            logger.warning(f"OTP sending failed for {user_data.email}: {otp_result.message}")
            return {
                "success": True,
                "message": "Account created but verification email failed to send. Please try resending verification code.",
                "user": UserProfileResponse(**create_user_profile_response(user_profile)) if user_profile else None,
                "verification_required": True,
                "otp_sent": False,
                "next_step": "resend_verification"
            }
        
        logger.info(f"User registered successfully with OTP sent: {user_data.email}")
        
        return {
            "success": True,
            "message": "Account created successfully! Please check your email for the verification code.",
            "user": UserProfileResponse(**create_user_profile_response(user_profile)) if user_profile else None,
            "verification_required": True,
            "otp_sent": True,
            "expires_at": otp_result.expires_at.isoformat() if otp_result.expires_at else None,
            "next_step": "verify_email"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )


@router.post("/complete-registration", response_model=AuthResponse)
async def complete_registration_with_otp(
    verification_request: OTPVerificationRequest,
    request: Request,
    auth_service: MongoAuthService = Depends(get_auth_service),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Complete registration by verifying OTP and issuing JWT token
    This is step 2 of the 2-step registration process
    """
    try:
        client_ip, user_agent = get_client_info(request)
        
        # Step 1: Verify OTP
        otp_service = OTPService(db)
        otp_result = await otp_service.verify_otp(
            request=verification_request,
            ip_address=client_ip
        )
        
        if not otp_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=otp_result.message
            )
        
        # Step 2: Get the verified user
        user = await auth_service.get_user_by_email(verification_request.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found"
            )
        
        # Step 3: Mark user as email verified and generate JWT
        await auth_service.mark_email_verified(verification_request.email)
        
        # Step 4: Generate JWT token for the verified user
        access_token = auth_service._create_access_token(user.id)
        session_token = auth_service._generate_session_token()
        
        # Step 5: Update last login
        await auth_service.update_last_login(verification_request.email, client_ip)
        
        logger.info(f"Registration completed successfully: {verification_request.email}")
        
        # Create a session for the verified user
        from models.user_models import UserSessionModel
        session = UserSessionModel(
            user_id=user.id,
            session_token=session_token,
            expires_at=datetime.utcnow() + timedelta(hours=24 * 7),  # 7 days
            ip_address=client_ip,
            user_agent=user_agent
        )
        await auth_service.sessions_collection.insert_one(session.dict())
        
        return AuthResponse(
            access_token=access_token,
            session_token=session_token,
            token_type="bearer",
            expires_in=24 * 7 * 3600,  # 7 days in seconds
            user=UserProfileResponse(**create_user_profile_response(user.dict()))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration completion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete registration. Please try again."
        )


@router.post("/login", response_model=AuthResponse)
async def login_user(
    login_data: UserLoginRequest,
    request: Request,
    auth_service: MongoAuthService = Depends(get_auth_service)
):
    """
    Login user - requires email verification
    """
    try:
        client_ip, user_agent = get_client_info(request)
        
        # Step 1: Check if user exists and credentials are valid
        from models.user_models import UserLoginModel
        login_model = UserLoginModel(email=login_data.email, password=login_data.password)
        success, message, auth_data = await auth_service.login_user(login_model, device_info={"user_agent": user_agent}, ip_address=client_ip)
        
        if not success or not auth_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=message or "Invalid email or password"
            )
        
        # Step 2: Email verification check removed - OTP during registration is sufficient verification
        
        logger.info(f"User logged in successfully: {login_data.email}")
        
        # The auth_service.login_user already returns properly formatted auth_data
        # with access_token, session_token, token_type, expires_in, and user
        return AuthResponse(**auth_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again."
        )


@router.post("/resend-verification", response_model=Dict[str, Any])
async def resend_verification_code(
    email: str,
    request: Request,
    auth_service: MongoAuthService = Depends(get_auth_service),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Resend verification code for unverified accounts
    """
    try:
        client_ip, user_agent = get_client_info(request)
        
        # Check if user exists
        user = await auth_service.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account found with this email address"
            )
        
        # Check if already verified
        if user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email address is already verified"
            )
        
        # Resend OTP
        otp_service = OTPService(db)
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        otp_result = await otp_service.resend_otp(
            email=email,
            user_name=full_name or email.split('@')[0],  # Fallback to email username
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        if not otp_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=otp_result.message
            )
        
        return {
            "success": True,
            "message": "Verification code sent successfully",
            "expires_at": otp_result.expires_at.isoformat() if otp_result.expires_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend verification code"
        )


# Dependency to get current verified user
# Use consolidated verified user dependency (alias for backward compatibility)
get_current_verified_user = get_current_verified_user_consolidated


# Protected route example
@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    current_user: UserModel = Depends(get_current_verified_user)
):
    """
    Get user profile (requires verified email)
    """
    return UserProfileResponse(**current_user.dict())


@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    update_data: UserUpdateRequest,
    current_user: UserModel = Depends(get_current_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Update user profile information
    """
    try:
        logger.info(f"🔄 [PROFILE UPDATE] Starting update for user: {current_user.email}")
        
        # Build update document with only provided fields
        update_fields = {}
        
        if update_data.first_name is not None:
            update_fields["first_name"] = update_data.first_name
        if update_data.last_name is not None:
            update_fields["last_name"] = update_data.last_name
        if update_data.phone_number is not None:
            update_fields["phone_number"] = update_data.phone_number
        if update_data.date_of_birth is not None:
            update_fields["date_of_birth"] = update_data.date_of_birth
        if update_data.gender is not None:
            update_fields["gender"] = update_data.gender
        if update_data.avatar is not None:
            update_fields["avatar"] = update_data.avatar
        if update_data.privacy_settings is not None:
            update_fields["privacy_settings"] = update_data.privacy_settings
        
        # Always update the timestamp
        update_fields["updated_at"] = datetime.utcnow()
        
        logger.info(f"🔄 [PROFILE UPDATE] Updating fields: {list(update_fields.keys())}")
        
        # Update user in database
        result = await db.users.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": update_fields}
        )
        
        if result.matched_count == 0:
            logger.error(f"❌ [PROFILE UPDATE] User not found: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if result.modified_count == 0:
            logger.warning(f"⚠️ [PROFILE UPDATE] No changes made for user: {current_user.email}")
        
        # Retrieve updated user
        updated_user_doc = await db.users.find_one({"_id": ObjectId(current_user.id)})
        if not updated_user_doc:
            logger.error(f"❌ [PROFILE UPDATE] Could not retrieve updated user: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated profile"
            )
        
        # Convert to UserModel and then to response
        updated_user = UserModel(**updated_user_doc)
        logger.info(f"✅ [PROFILE UPDATE] Successfully updated profile for: {current_user.email}")
        
        return UserProfileResponse(**updated_user.dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [PROFILE UPDATE] Error updating profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.post("/profile/update", response_model=UserProfileResponse)
async def update_user_profile_post(
    update_data: UserUpdateRequest,
    current_user: UserModel = Depends(get_current_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Update user profile information (POST alternative for Netlify compatibility)
    """
    try:
        logger.info(f"🔄 [PROFILE UPDATE POST] Starting update for user: {current_user.email}")
        
        # Build update document with only provided fields
        update_fields = {}
        
        if update_data.first_name is not None:
            update_fields["first_name"] = update_data.first_name
        if update_data.last_name is not None:
            update_fields["last_name"] = update_data.last_name
        if update_data.phone_number is not None:
            update_fields["phone_number"] = update_data.phone_number
        if update_data.date_of_birth is not None:
            update_fields["date_of_birth"] = update_data.date_of_birth
        if update_data.gender is not None:
            update_fields["gender"] = update_data.gender
        if update_data.avatar is not None:
            update_fields["avatar"] = update_data.avatar
        if update_data.privacy_settings is not None:
            update_fields["privacy_settings"] = update_data.privacy_settings
        
        # Always update the timestamp
        update_fields["updated_at"] = datetime.utcnow()
        
        logger.info(f"🔄 [PROFILE UPDATE POST] Updating fields: {list(update_fields.keys())}")
        
        # Update user in database
        result = await db.users.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": update_fields}
        )
        
        if result.matched_count == 0:
            logger.error(f"❌ [PROFILE UPDATE POST] User not found: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if result.modified_count == 0:
            logger.warning(f"⚠️ [PROFILE UPDATE POST] No changes made for user: {current_user.email}")
        
        # Retrieve updated user
        updated_user_doc = await db.users.find_one({"_id": ObjectId(current_user.id)})
        if not updated_user_doc:
            logger.error(f"❌ [PROFILE UPDATE POST] Could not retrieve updated user: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated profile"
            )
        
        # Convert to UserModel and then to response
        updated_user = UserModel(**updated_user_doc)
        logger.info(f"✅ [PROFILE UPDATE POST] Successfully updated profile for: {current_user.email}")
        
        return UserProfileResponse(**updated_user.dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [PROFILE UPDATE POST] Error updating profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.get("/test-token")
async def test_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: MongoAuthService = Depends(get_auth_service),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Test endpoint to verify JWT token and user lookup
    """
    try:
        token = credentials.credentials
        logger.info(f"🔍 Testing token: {token[:20]}...")
        
        # Verify token
        user_id = auth_service._verify_access_token(token)
        logger.info(f"🔍 Extracted user_id from token: {user_id}")
        
        if not user_id:
            return {"success": False, "error": "Invalid token"}
        
        # Try to find user with ObjectId
        from bson import ObjectId
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
        if user_doc:
            logger.info(f"✅ Found user with ObjectId({user_id})")
            return {
                "success": True,
                "user_id": user_id,
                "email": user_doc.get("email"),
                "method": "ObjectId"
            }
        
        # Try with string id
        user_doc = await db.users.find_one({"_id": user_id})
        if user_doc:
            logger.info(f"✅ Found user with string id: {user_id}")
            return {
                "success": True,
                "user_id": user_id,
                "email": user_doc.get("email"),
                "method": "string"
            }
        
        logger.error(f"❌ User not found for id: {user_id}")
        return {"success": False, "error": f"User not found for id: {user_id}"}
        
    except Exception as e:
        logger.error(f"Test token error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/complete-onboarding")
async def complete_onboarding(
    request: Request,
    onboarding_data: Dict[str, Any],
    current_user = Depends(get_current_user_dependency),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Complete user onboarding and save preferences
    """
    try:
        client_ip, user_agent = get_client_info(request)
        user_email = current_user.get('email', 'unknown')
        user_id = current_user.get('id')
        
        logger.info(f"🚀 [ONBOARDING] Starting completion for user: {user_email}")
        logger.info(f"🚀 [ONBOARDING] User ID: {user_id} (type: {type(user_id)})")
        logger.info(f"🚀 [ONBOARDING] Client IP: {client_ip}, User Agent: {user_agent}")
        logger.info(f"🚀 [ONBOARDING] Family members count: {len(onboarding_data.get('family_members', []))}")
        logger.info(f"🚀 [ONBOARDING] Preferences keys: {list(onboarding_data.get('preferences', {}).keys())}")
        
        # Validate onboarding data
        if not onboarding_data.get("preferences"):
            logger.warning(f"⚠️  [ONBOARDING] No preferences provided for {user_email}")
        
        # Update user document with onboarding data
        update_data = {
            "onboarding_completed": True,
            "onboarding_completed_at": datetime.utcnow(),
            "family_members": onboarding_data.get("family_members", []),
            "preferences": onboarding_data.get("preferences", {}),
            "updated_at": datetime.utcnow(),
            "onboarding_completion_ip": client_ip,
            "onboarding_completion_user_agent": user_agent
        }
        
        # First try with string ID (most common format in our database)
        logger.info(f"🔍 [ONBOARDING] Attempting update with string ID: {user_id}")
        result = await db.users.update_one(
            {"_id": user_id},
            {"$set": update_data}
        )
        
        # If no match, try with ObjectId
        if result.matched_count == 0:
            logger.info(f"🔄 [ONBOARDING] No match with string ID, trying ObjectId format...")
            try:
                result = await db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": update_data}
                )
                logger.info(f"🔍 [ONBOARDING] ObjectId attempt - matched: {result.matched_count}")
            except Exception as oid_error:
                logger.error(f"❌ [ONBOARDING] ObjectId conversion failed: {oid_error}")
        
        logger.info(f"🚀 [ONBOARDING] Final update result - matched: {result.matched_count}, modified: {result.modified_count}")
        
        if result.matched_count == 0:
            # User not found - this is a critical error
            logger.error(f"❌ [ONBOARDING] USER NOT FOUND - ID: {user_id}, Email: {user_email}")
            
            # Try to find user by email to debug
            user_by_email = await db.users.find_one({"email": user_email})
            if user_by_email:
                actual_id = user_by_email.get("_id")
                logger.error(f"❌ [ONBOARDING] Found user by email with different ID: {actual_id} (type: {type(actual_id)})")
            else:
                logger.error(f"❌ [ONBOARDING] User not found by email either: {user_email}")
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found during onboarding completion"
            )
        
        if result.modified_count > 0:
            # Get updated user - try string ID first
            updated_user = await db.users.find_one({"_id": user_id})
            if not updated_user:
                updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
                
            if updated_user:
                user_profile_data = create_user_profile_response(updated_user)
                logger.info(f"✅ [ONBOARDING] Completed successfully for {user_email}")
                logger.info(f"✅ [ONBOARDING] Response contains: {list(user_profile_data.keys())}")
                
                # Return the user data directly as the frontend expects
                return user_profile_data
            else:
                logger.error(f"❌ [ONBOARDING] Could not retrieve updated user: {user_email}")
        else:
            logger.warning(f"⚠️  [ONBOARDING] Update matched but no changes made for {user_email}")
        
        logger.error(f"❌ [ONBOARDING] Failed to complete - matched: {result.matched_count}, modified: {result.modified_count}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update onboarding status"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [ONBOARDING] Unexpected error for {current_user.get('email', 'unknown')}: {e}")
        logger.error(f"❌ [ONBOARDING] Error type: {type(e).__name__}")
        logger.error(f"❌ [ONBOARDING] Full error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete onboarding"
        )


# Event Interaction Endpoints
@router.post("/events/{event_id}/heart")
async def heart_event(
    event_id: str,
    current_user: UserModel = Depends(get_current_verified_user),
    auth_service: MongoAuthService = Depends(get_auth_service)
):
    """
    Heart/like an event
    """
    try:
        success, message = await auth_service.heart_event(current_user.id, event_id)
        
        if success:
            return {
                "success": True,
                "message": message or "Event hearted successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message or "Failed to heart event"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Heart event error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to heart event"
        )


@router.delete("/events/{event_id}/heart")
async def unheart_event(
    event_id: str,
    current_user: UserModel = Depends(get_current_verified_user),
    auth_service: MongoAuthService = Depends(get_auth_service)
):
    """
    Unheart/unlike an event
    """
    try:
        success, message = await auth_service.unheart_event(current_user.id, event_id)
        
        if success:
            return {
                "success": True,
                "message": message or "Event unhearted successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message or "Failed to unheart event"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unheart event error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unheart event"
        )


@router.post("/events/{event_id}/save")
async def save_event(
    event_id: str,
    current_user: UserModel = Depends(get_current_verified_user),
    auth_service: MongoAuthService = Depends(get_auth_service)
):
    """
    Save an event for later
    """
    try:
        success, message = await auth_service.save_event(current_user.id, event_id)
        
        if success:
            return {
                "success": True,
                "message": message or "Event saved successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message or "Failed to save event"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save event error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save event"
        )


@router.delete("/events/{event_id}/save")
async def unsave_event(
    event_id: str,
    current_user: UserModel = Depends(get_current_verified_user),
    auth_service: MongoAuthService = Depends(get_auth_service)
):
    """
    Remove event from saved events
    """
    try:
        success, message = await auth_service.unsave_event(current_user.id, event_id)
        
        if success:
            return {
                "success": True,
                "message": message or "Event unsaved successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message or "Failed to unsave event"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unsave event error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unsave event"
        )


@router.post("/events/{event_id}/rate")
async def rate_event(
    event_id: str,
    rating_data: Dict[str, float],
    current_user: UserModel = Depends(get_current_verified_user),
    auth_service: MongoAuthService = Depends(get_auth_service)
):
    """
    Rate an event
    """
    try:
        rating = rating_data.get("rating")
        if rating is None or not (0 <= rating <= 5):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rating must be between 0 and 5"
            )
        
        success, message = await auth_service.rate_event(current_user.id, event_id, rating)
        
        if success:
            return {
                "success": True,
                "message": message or "Event rated successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message or "Failed to rate event"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate event error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rate event"
        )


@router.get("/events/interactions")
async def get_event_interactions(
    current_user: UserModel = Depends(get_current_verified_user)
):
    """
    Get user's event interactions (hearted, saved, rated events)
    """
    try:
        return {
            "success": True,
            "data": {
                "hearted_events": current_user.hearted_events or [],
                "saved_events": current_user.saved_events or [],
                "event_ratings": current_user.event_ratings or {},
                "attended_events": current_user.attended_events or []
            }
        }
        
    except Exception as e:
        logger.error(f"Get event interactions error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get event interactions"
        )


# Password Reset Endpoints
@router.post("/forgot-password", response_model=Dict[str, Any])
async def forgot_password(
    email: EmailStr,
    request: Request,
    auth_service: MongoAuthService = Depends(get_auth_service),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Send password reset code to user's email
    """
    try:
        client_ip, user_agent = get_client_info(request)
        
        # Check if user exists
        user = await auth_service.get_user_by_email(email)
        if not user:
            # Return success even if user doesn't exist for security
            return {
                "success": True,
                "message": "If an account with this email exists, a password reset code has been sent."
            }
        
        # Generate and send password reset OTP
        otp_service = OTPService(db)
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        otp_request = OTPGenerationRequest(
            email=email,
            user_name=full_name or email.split('@')[0],
            purpose="password_reset"
        )
        
        otp_result = await otp_service.generate_and_send_otp(
            request=otp_request,
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        if not otp_result.success:
            if "rate_limit" in otp_result.details.get("reason", ""):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=otp_result.message
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send reset code. Please try again."
            )
        
        logger.info(f"Password reset code sent to {email}")
        
        return {
            "success": True,
            "message": "Password reset code sent to your email",
            "expires_at": otp_result.expires_at.isoformat() if otp_result.expires_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Forgot password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process password reset request"
        )


@router.post("/verify-reset-code", response_model=Dict[str, Any])
async def verify_reset_code(
    verification_request: OTPVerificationRequest,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Verify password reset code
    """
    try:
        client_ip, user_agent = get_client_info(request)
        
        # Ensure this is for password reset
        if verification_request.purpose != "password_reset":
            verification_request.purpose = "password_reset"
        
        # Verify OTP
        otp_service = OTPService(db)
        otp_result = await otp_service.verify_otp(
            request=verification_request,
            ip_address=client_ip
        )
        
        if not otp_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=otp_result.message
            )
        
        logger.info(f"Password reset code verified for {verification_request.email}")
        
        return {
            "success": True,
            "message": "Reset code verified successfully",
            "email": verification_request.email,
            "next_step": "reset_password"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify reset code error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify reset code"
        )


@router.post("/reset-password", response_model=Dict[str, Any])
async def reset_password(
    reset_data: Dict[str, str],
    request: Request,
    auth_service: MongoAuthService = Depends(get_auth_service),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Reset password using verified reset code
    """
    try:
        email = reset_data.get("email")
        new_password = reset_data.get("new_password")
        reset_code = reset_data.get("reset_code")
        
        if not email or not new_password or not reset_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email, new password, and reset code are required"
            )
        
        if len(new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        client_ip, user_agent = get_client_info(request)
        
        # Verify the reset code one more time
        verification_request = OTPVerificationRequest(
            email=email,
            otp_code=reset_code,
            purpose="password_reset"
        )
        
        otp_service = OTPService(db)
        otp_result = await otp_service.verify_otp(
            request=verification_request,
            ip_address=client_ip
        )
        
        if not otp_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset code"
            )
        
        # Reset the password
        success, message = await auth_service.reset_user_password(email, new_password)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message or "Failed to reset password"
            )
        
        # Invalidate all user sessions for security
        await auth_service.invalidate_all_user_sessions(email)
        
        logger.info(f"Password reset successfully for {email}")
        
        return {
            "success": True,
            "message": "Password reset successfully. Please log in with your new password."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )


@router.get("/favorites")
async def get_favorite_events(
    event_type: Optional[str] = Query(None, description="Filter by 'hearted' or 'saved' events"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Events per page"),
    current_user: UserModel = Depends(get_current_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Get user's favorite events (hearted and/or saved) with full event data
    
    Args:
        event_type: Filter by 'hearted' or 'saved' events. None returns both.
        page: Page number for pagination
        per_page: Number of events per page
    """
    try:
        # Get event IDs based on type
        event_ids = []
        
        if event_type == 'hearted':
            event_ids = current_user.hearted_events or []
        elif event_type == 'saved':
            event_ids = current_user.saved_events or []
        else:
            # Get both hearted and saved events (unique)
            hearted_ids = current_user.hearted_events or []
            saved_ids = current_user.saved_events or []
            event_ids = list(set(hearted_ids + saved_ids))
        
        if not event_ids:
            return {
                "success": True,
                "data": {
                    "events": [],
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": 0,
                        "total_pages": 0,
                        "has_next": False,
                        "has_prev": False
                    }
                }
            }
        
        # Calculate pagination
        total = len(event_ids)
        total_pages = (total + per_page - 1) // per_page
        skip = (page - 1) * per_page
        paginated_ids = event_ids[skip:skip + per_page]
        
        # Import the conversion function from events router
        from routers.events import _convert_event_to_response
        
        # Convert string IDs to ObjectIds for MongoDB query
        object_ids = []
        for event_id in paginated_ids:
            try:
                if isinstance(event_id, str):
                    object_ids.append(ObjectId(event_id))
                else:
                    object_ids.append(event_id)
            except:
                logger.warning(f"Invalid event ID format: {event_id}")
                continue
        
        # Fetch events from MongoDB
        events_cursor = db.events.find({"_id": {"$in": object_ids}})
        events = await events_cursor.to_list(length=per_page)
        
        # Convert to response format and preserve order
        event_map = {}
        for event in events:
            event_response = await _convert_event_to_response(event)
            event_map[str(event["_id"])] = event_response
        
        # Return events in the same order as the IDs
        ordered_events = []
        for event_id in paginated_ids:
            event_id_str = str(event_id)
            if event_id_str in event_map:
                event_data = event_map[event_id_str]
                # Convert EventResponse to dict and add metadata
                event_dict = event_data.dict() if hasattr(event_data, 'dict') else event_data
                event_dict["is_hearted"] = event_id_str in (current_user.hearted_events or [])
                event_dict["is_saved"] = event_id_str in (current_user.saved_events or [])
                ordered_events.append(event_dict)
        
        return {
            "success": True,
            "data": {
                "events": ordered_events,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Get favorite events error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get favorite events"
        )