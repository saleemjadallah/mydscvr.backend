#!/usr/bin/env python3
"""
Simplified MongoDB storage for Perplexity-extracted events
Stores events directly in processed format compatible with frontend
"""

import os
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import re
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, ConnectionFailure
from bson import ObjectId
from loguru import logger
from dotenv import load_dotenv

# Add backend path for deduplication
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Backend'))
from utils.deduplication import EventDeduplicator

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'Mongo.env'))

class PerplexityEventsStorage:
    """
    Simplified storage for Perplexity-extracted events
    """
    
    def __init__(self):
        # MongoDB connection
        self.mongodb_uri = os.getenv('Mongo_URI')
        self.database_name = os.getenv('MONGO_DB_NAME', 'DXB')
        
        if not self.mongodb_uri:
            raise ValueError("MongoDB URI not found. Set Mongo_URI in Mongo.env file.")
        
        try:
            self.client = MongoClient(
                self.mongodb_uri,
                serverSelectionTimeoutMS=5000,
                tlsInsecure=True
            )
            
            # Test connection
            self.client.admin.command('ping')
            
            self.db = self.client[self.database_name]
            self.events_collection = self.db['events']
            self.extraction_sessions = self.db['extraction_sessions']
            
            # Ensure indexes exist
            self._create_indexes()
            
            # Initialize deduplicator
            from motor.motor_asyncio import AsyncIOMotorClient
            self.async_client = AsyncIOMotorClient(self.mongodb_uri)
            self.async_db = self.async_client[self.database_name]
            self.deduplicator = EventDeduplicator(self.async_db)
            
            logger.info(f"✅ Connected to MongoDB: {self.database_name}")
            logger.info(f"✅ EventDeduplicator initialized")
            
        except ConnectionFailure as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise
    
    def parse_date_with_relative(self, date_input: str) -> Optional[datetime]:
        """
        Parse dates including relative dates like 'Today', 'Tomorrow', etc.
        """
        if not date_input or not isinstance(date_input, str):
            return None
        
        date_str = date_input.strip().lower()
        now = datetime.now()
        
        # Handle relative dates
        if date_str in ['today', 'tonight']:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_str in ['tomorrow']:
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_str in ['yesterday']:
            return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif 'this weekend' in date_str:
            # Find next Saturday
            days_ahead = 5 - now.weekday()  # Saturday is 5
            if days_ahead <= 0:
                days_ahead += 7
            return (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif 'next week' in date_str:
            days_ahead = 7 - now.weekday()  # Next Monday
            return (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Handle "in X days" format
        days_match = re.search(r'in (\d+) days?', date_str)
        if days_match:
            days = int(days_match.group(1))
            return (now + timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Handle day names (Monday, Tuesday, etc.)
        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day in enumerate(weekdays):
            if day in date_str:
                days_ahead = i - now.weekday()
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                return (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Try parsing as ISO format
        try:
            return datetime.fromisoformat(date_input.replace('Z', '+00:00'))
        except:
            pass
        
        # Try common date formats
        date_formats = [
            '%Y-%m-%d',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_input, fmt)
            except:
                continue
        
        logger.warning(f"Could not parse date: {date_input}")
        return None
    
    def _calculate_featured_status(self, event_data: dict, start_date: datetime) -> bool:
        """
        Calculate if an event should be featured based on multiple factors:
        - Family score (primary factor)
        - Date proximity (events happening sooner get priority)
        - Event quality indicators
        - Category diversity
        """
        try:
            # Base family score (0-100)
            family_score = event_data.get("family_score", 0)
            
            # Date proximity score - events happening sooner get higher scores
            now = datetime.now()
            days_until_event = (start_date - now).days
            
            if days_until_event < 0:  # Past events
                date_score = 0
            elif days_until_event == 0:  # Today
                date_score = 30
            elif days_until_event <= 3:  # Next 3 days
                date_score = 25
            elif days_until_event <= 7:  # This week
                date_score = 20
            elif days_until_event <= 30:  # This month
                date_score = 15
            else:  # Future events
                date_score = 10
            
            # Quality indicators
            quality_score = 0
            
            # Has good description
            description = event_data.get("description", "")
            if len(description) > 50:
                quality_score += 5
            
            # Has image
            if event_data.get("image_url") or event_data.get("image_urls"):
                quality_score += 5
            
            # Has venue information
            venue = event_data.get("venue", {})
            if isinstance(venue, dict) and venue.get("name"):
                quality_score += 5
            
            # Has pricing information
            price_data = event_data.get("price_data", {})
            if price_data or event_data.get("price"):
                quality_score += 5
            
            # Category diversity boost
            category_score = 0
            category = event_data.get("category", "").lower()
            high_priority_categories = [
                "family_activities", "cultural", "educational", 
                "entertainment", "festivals", "outdoor_activities"
            ]
            if category in high_priority_categories:
                category_score = 10
            
            # Calculate total score
            total_score = family_score + date_score + quality_score + category_score
            
            # Featured threshold - require high family score OR good combination of factors
            if family_score >= 85:  # High family score alone
                return True
            elif family_score >= 70 and date_score >= 20:  # Good family score + happening soon
                return True
            elif family_score >= 75 and quality_score >= 15:  # Good family score + high quality
                return True
            elif total_score >= 100:  # Overall high score
                return True
            else:
                return False
                
        except Exception as e:
            logger.warning(f"Error calculating featured status: {e}")
            # Fallback to simple family score check
            return event_data.get("family_score", 0) > 80
    
    def _create_indexes(self):
        """Create necessary indexes for optimal performance"""
        try:
            # Events collection indexes
            self.events_collection.create_index([
                ("title", 1), 
                ("venue_name", 1), 
                ("start_date", 1)
            ], unique=True, name="unique_event")
            
            self.events_collection.create_index([("start_date", 1)])
            self.events_collection.create_index([("area", 1)])
            self.events_collection.create_index([("primary_category", 1)])
            self.events_collection.create_index([("family_friendly", 1)])
            self.events_collection.create_index([("family_score", -1)])
            self.events_collection.create_index([("min_price", 1)])
            self.events_collection.create_index([("created_at", -1)])
            
            # Extraction sessions indexes
            self.extraction_sessions.create_index([("session_id", 1)], unique=True)
            self.extraction_sessions.create_index([("created_at", -1)])
            
            logger.info("✅ MongoDB indexes created successfully")
            
        except Exception as e:
            logger.error(f"❌ Error creating indexes: {e}")
    
    def transform_event_for_frontend(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Perplexity event data to match frontend Event model structure
        """
        try:
            # Generate a unique ID if not present
            event_id = str(ObjectId())
            
            # Construct venue object
            venue = {
                "id": event_id,
                "name": event_data.get("venue_name", "TBA"),
                "address": event_data.get("address", ""),
                "area": event_data.get("area", "Dubai"),
                "district": None,
                "city": "Dubai",
                "latitude": None,
                "longitude": None,
                "amenities": {
                    "parking": event_data.get("parking_available", True),
                    "metro_access": event_data.get("metro_accessible", True),
                    "wheelchair_accessible": event_data.get("special_needs_friendly", "unknown") == True
                },
                "parking_available": event_data.get("parking_available", True),
                "public_transport_access": event_data.get("metro_accessible", True)
            }
            
            # Construct pricing object
            pricing = {
                "base_price": float(event_data.get("min_price", 0)),
                "max_price": float(event_data.get("max_price") or event_data.get("min_price", 0)),
                "currency": event_data.get("currency", "AED"),
                "is_refundable": True,
                "pricing_notes": event_data.get("pricing_notes")
            }
            
            # Construct family suitability object
            family_suitability = {
                "min_age": event_data.get("child_age_min"),
                "max_age": event_data.get("child_age_max"),
                "recommended_age_range": f"{event_data.get('child_age_min', 0)}-{event_data.get('child_age_max', 99)}" if event_data.get('child_age_min') else "All ages",
                "stroller_friendly": event_data.get("stroller_accessible", True),
                "baby_changing": True,
                "nursing_friendly": True,
                "kid_menu_available": False,
                "educational_content": event_data.get("educational_value", "none") in ["medium", "high"],
                "notes": f"Family Score: {event_data.get('family_score', 0)}/100"
            }
            
            # Construct organizer info
            organizer_info = {
                "name": "Dubai Events",
                "description": "Verified event organizer",
                "verification_status": "verified",
                "contact_info": event_data.get("contact_info")
            }
            
            # Parse dates using enhanced date parser
            start_date = event_data.get("start_date")
            end_date = event_data.get("end_date")
            
            # Parse start_date
            if isinstance(start_date, str):
                parsed_start = self.parse_date_with_relative(start_date)
                start_date = parsed_start if parsed_start else datetime.now()
            elif not isinstance(start_date, datetime):
                start_date = datetime.now()
            
            # Parse end_date
            if isinstance(end_date, str):
                parsed_end = self.parse_date_with_relative(end_date)
                end_date = parsed_end
            elif not isinstance(end_date, datetime):
                end_date = None
            
            # If end_date is None, set it to start_date + 1 day for single-day events
            if not end_date:
                end_date = start_date + timedelta(days=1)
            
            # Primary category mapping
            category_mapping = {
                "family": "family_activities",
                "children": "kids_activities", 
                "educational": "educational",
                "outdoor": "outdoor_activities",
                "cultural": "cultural",
                "entertainment": "entertainment",
                "dining": "dining",
                "nightlife": "nightlife",
                "sports": "sports",
                "business": "business"
            }
            
            primary_category = event_data.get("primary_category", "entertainment")
            mapped_category = category_mapping.get(primary_category, primary_category)
            
            # Image URL handling
            image_urls = event_data.get("image_urls", [])
            primary_image = image_urls[0] if image_urls else "https://via.placeholder.com/800x400/E3F2FD/1976D2?text=Dubai+Event"
            
            # Construct the final event object
            transformed_event = {
                "_id": ObjectId(),
                "id": event_id,
                "title": event_data.get("title", "Untitled Event"),
                "description": event_data.get("description", ""),
                "short_description": event_data.get("ai_summary"),
                "ai_summary": event_data.get("ai_summary"),
                "family_score": event_data.get("family_score", 0),
                "categories": event_data.get("secondary_categories", []) + [primary_category],
                "quality_score": 85,  # Default quality score
                "image_url": primary_image,
                "category": mapped_category,
                "tags": event_data.get("target_audience", []),
                "start_date": start_date,
                "end_date": end_date,
                "venue": venue,
                "pricing": pricing,
                "family_suitability": family_suitability,
                "highlights": [],
                "included": [],
                "accessibility": [],
                "what_to_bring": [],
                "important_info": [],
                "cancellation_policy": "Please check with organizer",
                "organizer_info": organizer_info,
                "booking_required": event_data.get("booking_required", False),
                "available_slots": None,
                "max_capacity": None,
                "is_featured": self._calculate_featured_status(event_data, start_date),
                "is_trending": False,
                "rating": min(5.0, max(1.0, (event_data.get("family_score", 75) / 20))),
                "review_count": 0,
                "status": "active",  # Set status to active for API filtering
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                
                # Additional metadata for tracking
                "source": event_data.get("source", "Perplexity Search"),
                "source_url": event_data.get("source_url"),
                "extraction_metadata": {
                    "family_friendly": event_data.get("family_friendly", False),
                    "age_restrictions": event_data.get("age_restrictions"),
                    "primary_category_original": primary_category,
                    "extraction_timestamp": datetime.now().isoformat()
                },
                
                # Enhanced fields from Perplexity extraction
                "event_url": event_data.get("event_url"),
                "social_media": event_data.get("social_media"),
                "quality_metrics": event_data.get("quality_metrics"),
                "ticket_links": event_data.get("ticket_links", []),
                "contact_info": event_data.get("contact_info"),
                "target_audience": event_data.get("target_audience", []),
                "age_restrictions": event_data.get("age_restrictions"),
                "dress_code": event_data.get("dress_code"),
                "recurring": event_data.get("recurring"),
                "venue_type": event_data.get("venue_type"),
                "metro_accessible": event_data.get("metro_accessible"),
                "special_needs_friendly": event_data.get("special_needs_friendly"),
                "language_requirements": event_data.get("language_requirements"),
                "alcohol_served": event_data.get("alcohol_served"),
                "transportation_notes": event_data.get("transportation_notes"),
                "primary_category": event_data.get("primary_category"),
                "secondary_categories": event_data.get("secondary_categories", []),
                "event_type": event_data.get("event_type"),
                "indoor_outdoor": event_data.get("indoor_outdoor"),
                "special_occasion": event_data.get("special_occasion")
            }
            
            return transformed_event
            
        except Exception as e:
            logger.error(f"❌ Error transforming event data: {e}")
            logger.error(f"Event data: {json.dumps(event_data, indent=2)}")
            return None
    
    async def store_events(self, events_data: List[Dict[str, Any]], session_id: str) -> Dict[str, Any]:
        """
        Store extracted events to MongoDB with deduplication
        """
        results = {
            "total_processed": len(events_data),
            "stored_count": 0,
            "updated_count": 0,
            "skipped_count": 0,
            "duplicates_prevented": 0,
            "errors": []
        }
        
        for event_data in events_data:
            try:
                # Transform event data
                transformed_event = self.transform_event_for_frontend(event_data)
                
                if not transformed_event:
                    results["skipped_count"] += 1
                    continue
                
                # Check for duplicates using the sophisticated deduplicator
                try:
                    is_duplicate = await self.deduplicator.is_duplicate_event(transformed_event)
                    if is_duplicate:
                        results["duplicates_prevented"] += 1
                        logger.info(f"🔄 Duplicate detected and skipped: {transformed_event['title']}")
                        continue
                except Exception as e:
                    logger.warning(f"⚠️ Deduplication check failed for '{transformed_event['title']}': {e}")
                    # Continue with insertion if deduplication fails
                
                # Try to insert or update
                try:
                    result = self.events_collection.insert_one(transformed_event)
                    results["stored_count"] += 1
                    logger.info(f"✅ Stored event: {transformed_event['title']}")
                    
                except DuplicateKeyError:
                    # Update existing event (this is a fallback for exact key matches)
                    filter_query = {
                        "title": transformed_event["title"],
                        "venue.name": transformed_event["venue"]["name"],
                        "start_date": transformed_event["start_date"]
                    }
                    
                    # Remove _id from update data since it's immutable
                    update_event = {k: v for k, v in transformed_event.items() if k != '_id'}
                    update_data = {
                        "$set": {
                            **update_event,
                            "updated_at": datetime.now()
                        }
                    }
                    
                    result = self.events_collection.update_one(filter_query, update_data)
                    if result.modified_count > 0:
                        results["updated_count"] += 1
                        logger.info(f"🔄 Updated event: {transformed_event['title']}")
                    else:
                        results["skipped_count"] += 1
                        logger.info(f"⚠️ No changes for event: {transformed_event['title']}")
                
            except Exception as e:
                error_msg = f"Error processing event '{event_data.get('title', 'Unknown')}': {e}"
                logger.error(f"❌ {error_msg}")
                results["errors"].append(error_msg)
                results["skipped_count"] += 1
        
        logger.info(f"📊 Storage results: {results['stored_count']} stored, {results['updated_count']} updated, {results['skipped_count']} skipped")
        return results
    
    def create_extraction_session(self, session_name: str, session_data: Dict[str, Any] = None) -> str:
        """
        Create an extraction session record
        """
        session_id = str(ObjectId())
        
        if session_data is None:
            session_data = {}
        
        session_record = {
            "_id": ObjectId(),
            "session_id": session_id,
            "session_name": session_name,
            "started_at": datetime.now(),
            "status": "running",
            "search_queries": session_data.get("search_queries", []) if isinstance(session_data, dict) else [],
            "total_queries": len(session_data.get("search_queries", [])) if isinstance(session_data, dict) else 0,
            "completed_queries": 0,
            "total_events_found": 0,
            "events_stored": 0,
            "extraction_method": "perplexity",
            "created_at": datetime.now()
        }
        
        try:
            self.extraction_sessions.insert_one(session_record)
            logger.info(f"✅ Created extraction session: {session_id}")
            return session_id
        except Exception as e:
            logger.error(f"❌ Error creating extraction session: {e}")
            return session_id
    
    def update_extraction_session(self, session_id: str, update_data: Dict[str, Any]):
        """
        Update extraction session status
        """
        try:
            filter_query = {"session_id": session_id}
            update_query = {
                "$set": {
                    **update_data,
                    "updated_at": datetime.now()
                }
            }
            
            result = self.extraction_sessions.update_one(filter_query, update_query)
            if result.modified_count > 0:
                logger.info(f"✅ Updated extraction session: {session_id}")
            
        except Exception as e:
            logger.error(f"❌ Error updating extraction session: {e}")
    
    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recently stored events
        """
        try:
            events = list(self.events_collection.find(
                {},
                {"_id": 0}  # Exclude MongoDB _id from results
            ).sort("created_at", DESCENDING).limit(limit))
            
            logger.info(f"📋 Retrieved {len(events)} recent events")
            return events
            
        except Exception as e:
            logger.error(f"❌ Error retrieving recent events: {e}")
            return []
    
    def get_family_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get family-friendly events with high family scores
        """
        try:
            events = list(self.events_collection.find(
                {"extraction_metadata.family_friendly": True},
                {"_id": 0}
            ).sort("family_score", DESCENDING).limit(limit))
            
            logger.info(f"👨‍👩‍👧‍👦 Retrieved {len(events)} family events")
            return events
            
        except Exception as e:
            logger.error(f"❌ Error retrieving family events: {e}")
            return []
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics
        """
        try:
            total_events = self.events_collection.count_documents({})
            family_events = self.events_collection.count_documents({
                "extraction_metadata.family_friendly": True
            })
            recent_events = self.events_collection.count_documents({
                "created_at": {"$gte": datetime.now().replace(hour=0, minute=0, second=0)}
            })
            
            stats = {
                "total_events": total_events,
                "family_events": family_events,
                "adult_events": total_events - family_events,
                "recent_events_today": recent_events,
                "database_name": self.database_name,
                "last_updated": datetime.now().isoformat()
            }
            
            logger.info(f"📊 Database stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting database stats: {e}")
            return {}
    
    def close(self):
        """Close MongoDB connection"""
        if hasattr(self, 'client'):
            self.client.close()
            logger.info("🔌 MongoDB connection closed")

# Example usage
if __name__ == "__main__":
    # Test the storage system
    storage = PerplexityEventsStorage()
    
    # Get database stats
    stats = storage.get_database_stats()
    print(f"Database Stats: {json.dumps(stats, indent=2)}")
    
    # Get recent events
    recent_events = storage.get_recent_events(5)
    print(f"Recent Events: {len(recent_events)}")
    
    # Close connection
    storage.close() 