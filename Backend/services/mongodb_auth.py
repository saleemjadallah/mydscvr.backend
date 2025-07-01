from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import jwt
import secrets
import logging
from email_validator import validate_email, EmailNotValidError

from models.user_models import (
    UserModel, UserRegistrationModel, UserLoginModel, 
    UserUpdateModel, OnboardingCompletionModel, UserSessionModel
)
from config import settings

logger = logging.getLogger(__name__)


class MongoAuthService:
    """MongoDB-based authentication service"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.db = database
        self.users_collection = database.users
        self.sessions_collection = database.user_sessions
        
        # Import centralized JWT config
        from utils.jwt_config import JWTConfig
        self.jwt_config = JWTConfig
        
        # Legacy properties for backward compatibility
        self.jwt_secret = JWTConfig.SECRET_KEY
        self.jwt_algorithm = JWTConfig.ALGORITHM
        self.access_token_expire_hours = JWTConfig.ACCESS_TOKEN_EXPIRE_HOURS
        
    async def create_indexes(self):
        """Create necessary database indexes"""
        try:
            # Create unique index on email
            await self.users_collection.create_index("email", unique=True)
            
            # Create index on session tokens
            await self.sessions_collection.create_index("session_token", unique=True)
            await self.sessions_collection.create_index("user_id")
            await self.sessions_collection.create_index("expires_at", expireAfterSeconds=0)
            
            logger.info("MongoDB auth indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating auth indexes: {e}")
    
    def _generate_session_token(self) -> str:
        """Generate a secure session token"""
        return secrets.token_urlsafe(32)
    
    def _create_access_token(self, user_id: str, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token using centralized config"""
        to_encode = {
            "sub": user_id,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        return self.jwt_config.create_access_token(to_encode, expires_delta, use_extended_expiry=True)
    
    def _verify_access_token(self, token: str) -> Optional[str]:
        """Verify JWT access token and return user_id using centralized config"""
        return self.jwt_config.get_user_id_from_token(token)
    
    async def register_user(self, registration_data: UserRegistrationModel, email_verified: bool = False) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Register a new user
        Returns: (success, message, user_data)
        """
        try:
            # Validate email format
            try:
                valid_email = validate_email(registration_data.email)
                registration_data.email = valid_email.email
            except EmailNotValidError as e:
                return False, f"Invalid email format: {str(e)}", None
            
            # Check if user already exists
            existing_user = await self.users_collection.find_one({"email": registration_data.email})
            if existing_user:
                return False, "User with this email already exists", None
            
            # Create new user
            user_data = UserModel(
                email=registration_data.email,
                password_hash=UserModel.hash_password(registration_data.password),
                first_name=registration_data.first_name,
                last_name=registration_data.last_name,
                phone_number=registration_data.phone_number,
                email_verified=email_verified,
                is_email_verified=email_verified,  # Ensure both fields are consistent
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Insert user into database
            result = await self.users_collection.insert_one(user_data.dict(by_alias=True))
            user_data.id = str(result.inserted_id)
            
            logger.info(f"User registered successfully: {registration_data.email}")
            logger.info(f"User ID after registration: {user_data.id}")
            logger.info(f"MongoDB _id: {result.inserted_id}")
            return True, "User registered successfully", user_data.to_profile_dict()
            
        except DuplicateKeyError:
            return False, "User with this email already exists", None
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            return False, f"Registration failed: {str(e)}", None
    
    async def login_user(self, login_data: UserLoginModel, device_info: Optional[Dict[str, str]] = None, ip_address: Optional[str] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Authenticate user and create session
        Returns: (success, message, auth_data)
        """
        try:
            # Find user by email
            user_doc = await self.users_collection.find_one({"email": login_data.email})
            if not user_doc:
                return False, "Invalid email or password", None
            
            # Create user model
            user = UserModel(**user_doc)
            
            # Verify password
            if not user.verify_password(login_data.password):
                return False, "Invalid email or password", None
            
            # Check if user is active
            if not user.is_active:
                return False, "Account is deactivated", None
            
            # Generate tokens
            access_token = self._create_access_token(user.id)
            session_token = self._generate_session_token()
            
            # Create session
            session = UserSessionModel(
                user_id=user.id,
                session_token=session_token,
                expires_at=datetime.utcnow() + timedelta(hours=self.access_token_expire_hours),
                device_info=device_info,
                ip_address=ip_address
            )
            
            # Save session to database
            await self.sessions_collection.insert_one(session.dict())
            
            # Update user login stats - use the same ID format as in database
            await self.users_collection.update_one(
                {"_id": user_doc["_id"]},  # Use the same _id format as found in database
                {
                    "$set": {"last_login_at": datetime.utcnow()},
                    "$inc": {"login_count": 1}
                }
            )
            
            logger.info(f"User logged in successfully: {login_data.email}")
            
            return True, "Login successful", {
                "access_token": access_token,
                "session_token": session_token,
                "token_type": "bearer",
                "expires_in": self.access_token_expire_hours * 3600,
                "user": user.to_profile_dict()
            }
            
        except Exception as e:
            logger.error(f"Error during login: {e}")
            return False, f"Login failed: {str(e)}", None
    
    async def get_current_user(self, token: str) -> Optional[UserModel]:
        """Get current user from access token"""
        try:
            from bson import ObjectId
            user_id = self._verify_access_token(token)
            if not user_id:
                return None
            
            logger.info(f"Getting user with id from token: {user_id}")
            
            # Try with ObjectId first
            user_doc = await self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user_doc:
                logger.warning(f"No user found for ObjectId({user_id}), trying string format...")
                # Try with string ID (some users have string IDs)
                user_doc = await self.users_collection.find_one({"_id": user_id})
                if not user_doc:
                    logger.error(f"No user found with either ObjectId or string format: {user_id}")
                    return None
                else:
                    logger.info(f"Found user with string ID format")
            else:
                logger.info(f"Found user with ObjectId format")
            
            user = UserModel(**user_doc)
            logger.info(f"Loaded user {user.email} with model id: {user.id}")
            return user
            
        except Exception as e:
            logger.error(f"Error getting current user: {e}")
            return None
    
    async def logout_user(self, session_token: str) -> bool:
        """Logout user by invalidating session"""
        try:
            result = await self.sessions_collection.delete_one({"session_token": session_token})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error during logout: {e}")
            return False
    
    async def update_user_profile(self, user_id: str, update_data: UserUpdateModel) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Update user profile information"""
        try:
            # Prepare update data
            update_fields = {
                "updated_at": datetime.utcnow()
            }
            
            # Add non-None fields to update
            for field, value in update_data.dict(exclude_unset=True).items():
                if value is not None:
                    update_fields[field] = value
            
            # First try with string ID (most common format in our database)
            result = await self.users_collection.update_one(
                {"_id": user_id},
                {"$set": update_fields}
            )
            
            # If no match, try with ObjectId format
            if result.matched_count == 0:
                from bson import ObjectId
                result = await self.users_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": update_fields}
                )
            
            if result.matched_count == 0:
                return False, "User not found", None
            
            # Get updated user - try string ID first, then ObjectId
            user_doc = await self.users_collection.find_one({"_id": user_id})
            if not user_doc:
                try:
                    from bson import ObjectId
                    user_doc = await self.users_collection.find_one({"_id": ObjectId(user_id)})
                except:
                    pass
            
            if not user_doc:
                return False, "Could not retrieve updated user", None
            
            user = UserModel(**user_doc)
            
            logger.info(f"User profile updated: {user_id}")
            return True, "Profile updated successfully", user.to_profile_dict()
            
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            return False, f"Update failed: {str(e)}", None
    
    async def complete_onboarding(self, user_id: str, onboarding_data: OnboardingCompletionModel) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Complete user onboarding process"""
        try:
            # Update user with onboarding data
            update_fields = {
                "family_members": [member.dict() for member in onboarding_data.family_members],
                "preferences": onboarding_data.preferences.dict(),
                "onboarding_completed": True,
                "onboarding_completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # First try with string ID (most common format in our database)
            logger.info(f"🔍 [ONBOARDING_SERVICE] Attempting update with string ID: {user_id}")
            result = await self.users_collection.update_one(
                {"_id": user_id},
                {"$set": update_fields}
            )
            
            # If no match, try with ObjectId format
            if result.matched_count == 0:
                logger.info(f"🔄 [ONBOARDING_SERVICE] No match with string ID, trying ObjectId format...")
                try:
                    result = await self.users_collection.update_one(
                        {"_id": ObjectId(user_id)},
                        {"$set": update_fields}
                    )
                    logger.info(f"🔍 [ONBOARDING_SERVICE] ObjectId attempt - matched: {result.matched_count}")
                except Exception as oid_error:
                    logger.error(f"❌ [ONBOARDING_SERVICE] ObjectId conversion failed: {oid_error}")
            
            if result.matched_count == 0:
                logger.error(f"❌ [ONBOARDING_SERVICE] User not found with ID: {user_id}")
                return False, "User not found", None
            
            # Get updated user - try string ID first, then ObjectId
            user_doc = await self.users_collection.find_one({"_id": user_id})
            if not user_doc:
                try:
                    user_doc = await self.users_collection.find_one({"_id": ObjectId(user_id)})
                except:
                    pass
            
            if not user_doc:
                logger.error(f"❌ [ONBOARDING_SERVICE] Could not retrieve updated user: {user_id}")
                return False, "Could not retrieve updated user", None
            
            user = UserModel(**user_doc)
            
            logger.info(f"✅ [ONBOARDING_SERVICE] Onboarding completed for user: {user_id}")
            return True, "Onboarding completed successfully", user.to_profile_dict()
            
        except Exception as e:
            logger.error(f"❌ [ONBOARDING_SERVICE] Error completing onboarding: {e}")
            return False, f"Onboarding completion failed: {str(e)}", None
    
    async def verify_email(self, user_id: str) -> bool:
        """Mark user email as verified"""
        try:
            from bson import ObjectId
            result = await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"is_email_verified": True, "updated_at": datetime.utcnow()}}
            )
            return result.matched_count > 0
        except Exception as e:
            logger.error(f"Error verifying email: {e}")
            return False
    
    async def change_password(self, user_id: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        """Change user password"""
        try:
            # Get current user
            from bson import ObjectId
            user_doc = await self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user_doc:
                return False, "User not found"
            
            user = UserModel(**user_doc)
            
            # Verify old password
            if not user.verify_password(old_password):
                return False, "Invalid current password"
            
            # Update password
            new_password_hash = UserModel.hash_password(new_password)
            result = await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"password_hash": new_password_hash, "updated_at": datetime.utcnow()}}
            )
            
            if result.matched_count == 0:
                return False, "Failed to update password"
            
            # Invalidate all user sessions
            await self.sessions_collection.delete_many({"user_id": user_id})
            
            logger.info(f"Password changed for user: {user_id}")
            return True, "Password changed successfully"
            
        except Exception as e:
            logger.error(f"Error changing password: {e}")
            return False, f"Password change failed: {str(e)}"
    
    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate user account"""
        try:
            from bson import ObjectId
            result = await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            
            # Invalidate all user sessions
            await self.sessions_collection.delete_many({"user_id": user_id})
            
            return result.matched_count > 0
        except Exception as e:
            logger.error(f"Error deactivating user: {e}")
            return False
    
    async def get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics"""
        try:
            total_users = await self.users_collection.count_documents({})
            active_users = await self.users_collection.count_documents({"is_active": True})
            verified_users = await self.users_collection.count_documents({"is_email_verified": True})
            onboarded_users = await self.users_collection.count_documents({"onboarding_completed": True})
            
            return {
                "total_users": total_users,
                "active_users": active_users,
                "verified_users": verified_users,
                "onboarded_users": onboarded_users,
                "verification_rate": verified_users / total_users if total_users > 0 else 0,
                "onboarding_completion_rate": onboarded_users / total_users if total_users > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {}
    
    # Event Interaction Methods
    async def heart_event(self, user_id: str, event_id: str) -> Tuple[bool, str]:
        """Add event to user's hearted events"""
        try:
            # Try to find user with ObjectId first
            from bson import ObjectId
            user_doc = await self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user_doc:
                # Try with string ID
                user_doc = await self.users_collection.find_one({"_id": user_id})
                if not user_doc:
                    logger.error(f"User not found for heart_event: {user_id}")
                    return False, "User not found"
            
            hearted_events = user_doc.get("hearted_events", [])
            if event_id in hearted_events:
                return False, "Event already hearted"
            
            # Update with same ID format as found
            user_filter = {"_id": ObjectId(user_id)} if isinstance(user_doc["_id"], ObjectId) else {"_id": user_id}
            
            result = await self.users_collection.update_one(
                user_filter,
                {
                    "$addToSet": {"hearted_events": event_id},
                    "$set": {
                        f"event_interactions.{event_id}.hearted_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.matched_count > 0:
                logger.info(f"User {user_id} hearted event {event_id}")
                return True, "Event hearted successfully"
            else:
                return False, "Failed to heart event"
                
        except Exception as e:
            logger.error(f"Error hearting event: {e}")
            return False, f"Failed to heart event: {str(e)}"
    
    async def unheart_event(self, user_id: str, event_id: str) -> Tuple[bool, str]:
        """Remove event from user's hearted events"""
        try:
            from bson import ObjectId
            
            # Try with ObjectId first
            result = await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$pull": {"hearted_events": event_id},
                    "$unset": {f"event_interactions.{event_id}.hearted_at": ""},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
            # If no match, try with string ID
            if result.matched_count == 0:
                result = await self.users_collection.update_one(
                    {"_id": user_id},
                    {
                        "$pull": {"hearted_events": event_id},
                        "$unset": {f"event_interactions.{event_id}.hearted_at": ""},
                        "$set": {"updated_at": datetime.utcnow()}
                    }
                )
            
            if result.matched_count > 0:
                logger.info(f"User {user_id} unhearted event {event_id}")
                return True, "Event unhearted successfully"
            else:
                return False, "User not found"
                
        except Exception as e:
            logger.error(f"Error unhearting event: {e}")
            return False, f"Failed to unheart event: {str(e)}"
    
    async def save_event(self, user_id: str, event_id: str) -> Tuple[bool, str]:
        """Add event to user's saved events"""
        try:
            # Try to find user with ObjectId first
            from bson import ObjectId
            user_doc = await self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user_doc:
                # Try with string ID
                user_doc = await self.users_collection.find_one({"_id": user_id})
                if not user_doc:
                    logger.error(f"User not found for save_event: {user_id}")
                    return False, "User not found"
            
            saved_events = user_doc.get("saved_events", [])
            if event_id in saved_events:
                return False, "Event already saved"
            
            # Update with same ID format as found
            user_filter = {"_id": ObjectId(user_id)} if isinstance(user_doc["_id"], ObjectId) else {"_id": user_id}
            
            result = await self.users_collection.update_one(
                user_filter,
                {
                    "$addToSet": {"saved_events": event_id},
                    "$set": {
                        f"event_interactions.{event_id}.saved_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.matched_count > 0:
                logger.info(f"User {user_id} saved event {event_id}")
                return True, "Event saved successfully"
            else:
                return False, "Failed to save event"
                
        except Exception as e:
            logger.error(f"Error saving event: {e}")
            return False, f"Failed to save event: {str(e)}"
    
    async def unsave_event(self, user_id: str, event_id: str) -> Tuple[bool, str]:
        """Remove event from user's saved events"""
        try:
            from bson import ObjectId
            
            # Try with ObjectId first
            result = await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$pull": {"saved_events": event_id},
                    "$unset": {f"event_interactions.{event_id}.saved_at": ""},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
            # If no match, try with string ID
            if result.matched_count == 0:
                result = await self.users_collection.update_one(
                    {"_id": user_id},
                    {
                        "$pull": {"saved_events": event_id},
                        "$unset": {f"event_interactions.{event_id}.saved_at": ""},
                        "$set": {"updated_at": datetime.utcnow()}
                    }
                )
            
            if result.matched_count > 0:
                logger.info(f"User {user_id} unsaved event {event_id}")
                return True, "Event unsaved successfully"
            else:
                return False, "User not found"
                
        except Exception as e:
            logger.error(f"Error unsaving event: {e}")
            return False, f"Failed to unsave event: {str(e)}"
    
    async def rate_event(self, user_id: str, event_id: str, rating: float) -> Tuple[bool, str]:
        """Rate an event (1-5 stars)"""
        try:
            if not (1.0 <= rating <= 5.0):
                return False, "Rating must be between 1 and 5"
            
            from bson import ObjectId
            
            # Try with ObjectId first
            result = await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        f"event_ratings.{event_id}": rating,
                        f"event_interactions.{event_id}.rated_at": datetime.utcnow(),
                        f"event_interactions.{event_id}.rating": rating,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            # If no match, try with string ID
            if result.matched_count == 0:
                result = await self.users_collection.update_one(
                    {"_id": user_id},
                    {
                        "$set": {
                            f"event_ratings.{event_id}": rating,
                            f"event_interactions.{event_id}.rated_at": datetime.utcnow(),
                            f"event_interactions.{event_id}.rating": rating,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
            
            if result.matched_count > 0:
                logger.info(f"User {user_id} rated event {event_id} with {rating} stars")
                return True, "Event rated successfully"
            else:
                return False, "User not found"
                
        except Exception as e:
            logger.error(f"Error rating event: {e}")
            return False, f"Failed to rate event: {str(e)}"
    
    async def get_user_event_interactions(self, user_id: str) -> Dict[str, Any]:
        """Get all event interactions for a user"""
        try:
            from bson import ObjectId
            user_doc = await self.users_collection.find_one(
                {"_id": ObjectId(user_id)},
                {
                    "saved_events": 1,
                    "hearted_events": 1,
                    "attended_events": 1,
                    "event_ratings": 1,
                    "event_interactions": 1
                }
            )
            
            if not user_doc:
                return {}
            
            return {
                "saved_events": user_doc.get("saved_events", []),
                "hearted_events": user_doc.get("hearted_events", []),
                "attended_events": user_doc.get("attended_events", []),
                "event_ratings": user_doc.get("event_ratings", {}),
                "event_interactions": user_doc.get("event_interactions", {})
            }
            
        except Exception as e:
            logger.error(f"Error getting user event interactions: {e}")
            return {}
    
    async def mark_email_verified(self, email: str) -> bool:
        """
        Mark user's email as verified
        """
        try:
            result = await self.users_collection.update_one(
                {"email": email},
                {
                    "$set": {
                        "is_email_verified": True,
                        "email_verified": True,  # Keep for backward compatibility
                        "email_verified_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.matched_count > 0:
                logger.info(f"Email marked as verified for: {email}")
                return True
            else:
                logger.warning(f"No user found to mark email verified: {email}")
                return False
                
        except Exception as e:
            logger.error(f"Error marking email as verified: {e}")
            return False
    
    async def get_user_by_email(self, email: str) -> Optional[UserModel]:
        """
        Get user by email address
        """
        try:
            user_doc = await self.users_collection.find_one({"email": email})
            if user_doc:
                # The UserModel expects "_id" field due to alias="_id" in the model
                # Don't add a separate "id" field as it will conflict
                logger.info(f"Found user document for email {email} with _id: {user_doc['_id']}")
                user = UserModel(**user_doc)
                logger.info(f"Created UserModel with id: {user.id}")
                return user
            return None
            
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            return None
    
    async def update_last_login(self, email: str, ip_address: Optional[str] = None) -> bool:
        """
        Update user's last login timestamp and IP
        """
        try:
            update_data = {
                "last_login": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            if ip_address:
                update_data["last_login_ip"] = ip_address
            
            result = await self.users_collection.update_one(
                {"email": email},
                {"$set": update_data}
            )
            
            return result.matched_count > 0
            
        except Exception as e:
            logger.error(f"Error updating last login: {e}")
            return False
    
    async def reset_user_password(self, email: str, new_password: str) -> Tuple[bool, str]:
        """
        Reset user's password
        """
        try:
            # Validate password length
            if len(new_password) < 8:
                return False, "Password must be at least 8 characters long"
            
            # Hash the new password
            password_hash = UserModel.hash_password(new_password)
            
            # Update user password
            result = await self.users_collection.update_one(
                {"email": email},
                {
                    "$set": {
                        "password_hash": password_hash,
                        "updated_at": datetime.utcnow(),
                        "password_reset_at": datetime.utcnow()
                    }
                }
            )
            
            if result.matched_count > 0:
                logger.info(f"Password reset successfully for: {email}")
                return True, "Password reset successfully"
            else:
                logger.warning(f"No user found for password reset: {email}")
                return False, "User not found"
                
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            return False, "Failed to reset password"
    
    async def invalidate_all_user_sessions(self, email: str) -> bool:
        """
        Invalidate all active sessions for a user (for security after password reset)
        """
        try:
            # Get user to find their ID
            user = await self.get_user_by_email(email)
            if not user:
                return False
            
            # Delete all sessions for this user
            result = await self.sessions_collection.delete_many({"user_id": user.id})
            
            logger.info(f"Invalidated {result.deleted_count} sessions for user: {email}")
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating user sessions: {e}")
            return False