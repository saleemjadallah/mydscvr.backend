#!/usr/bin/env python3
"""
AI Image Generation Service for Dubai Events
Uses DALL-E 3 to generate contextual images for events
"""

import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
from loguru import logger
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import base64
import hashlib

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'AI_API.env'))

class AIImageService:
    """
    AI Image Generation Service using DALL-E 3
    Generates contextual images for Dubai events with smart prompting
    """
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required but not set")
        
        self.base_url = "https://api.openai.com/v1/images/generations"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Configure logging
        logger.add("logs/ai_image_service.log", rotation="10 MB", retention="7 days")
        
        # Image generation cache to avoid regenerating similar events
        self.generation_cache = {}
        
        # Category-specific prompt templates
        self.category_prompts = {
            "nightlife": "vibrant nightclub atmosphere, neon lights, energetic crowd, Dubai skyline at night",
            "dining": "elegant restaurant setting, fine dining ambiance, sophisticated atmosphere", 
            "family": "family-friendly venue, bright welcoming atmosphere, children and parents enjoying activities",
            "cultural": "cultural venue, traditional meets modern Dubai architecture, heritage elements",
            "outdoor": "outdoor event setting with Dubai skyline background, palm trees, modern architecture",
            "entertainment": "live performance venue, stage lighting, audience engagement, professional entertainment",
            "sports": "sports facility, athletic activities, modern Dubai sports venues",
            "business": "professional conference setting, modern business environment, Dubai corporate atmosphere",
            "music": "concert venue, stage with lighting, musical performance atmosphere",
            "arts": "art gallery or creative space, contemporary Dubai arts scene",
            "shopping": "luxury shopping environment, modern Dubai mall atmosphere",
            "educational": "learning environment, workshop setting, educational activities",
            "fitness": "modern fitness facility, wellness atmosphere, healthy lifestyle",
            "technology": "tech event space, modern conference setting, innovation atmosphere",
            "health_wellness": "serene wellness center, meditation space, peaceful atmosphere, yoga studio, holistic health environment, zen ambiance",
            "workshops": "hands-on workshop space, creative learning environment, interactive session setting",
            "networking": "professional networking venue, business meetup atmosphere, modern conference space",
            "festivals": "festive outdoor setting, celebration atmosphere, community gathering",
            "seasonal": "seasonal themed event space, holiday decorations, festive atmosphere"
        }
        
        # Venue-specific enhancements
        self.venue_keywords = {
            "burj": "iconic Burj Khalifa backdrop, luxury Dubai setting",
            "marina": "Dubai Marina waterfront, modern skyscrapers, marina views",
            "downtown": "Downtown Dubai, urban sophistication, modern architecture",
            "jumeirah": "Jumeirah beachfront, coastal Dubai, luxury resort atmosphere",
            "mall": "luxury shopping mall interior, modern retail environment",
            "hotel": "luxury hotel setting, premium hospitality atmosphere",
            "beach": "Dubai beach setting, coastal views, resort atmosphere",
            "desert": "Dubai desert setting, traditional meets modern"
        }
        
    def _create_cache_key(self, event: Dict[str, Any]) -> str:
        """Create a cache key for similar events to avoid regeneration"""
        key_components = [
            event.get('primary_category', ''),
            event.get('venue', {}).get('name', '').lower(),
            event.get('venue', {}).get('area', '').lower()
        ]
        key_string = "_".join(filter(None, key_components))
        return hashlib.md5(key_string.encode()).hexdigest()[:12]
    
    def _create_event_prompt(self, event: Dict[str, Any]) -> str:
        """Create optimized DALL-E prompt for event images"""
        
        # Base prompt
        prompt_parts = ["Professional event photography in Dubai"]
        
        # Add venue context
        venue_name = event.get('venue', {}).get('name', '')
        venue_area = event.get('venue', {}).get('area', '')
        
        if venue_name:
            prompt_parts.append(f"at {venue_name}")
            
        if venue_area:
            prompt_parts.append(f"in {venue_area}")
        
        # Check for specific event types in title/description for better prompting
        title = event.get('title', '').lower()
        description = event.get('description', '').lower()
        event_text = f"{title} {description}"
        
        # Special handling for meditation/wellness events
        if any(word in event_text for word in ['meditation', 'breathwork', 'mindfulness', 'zen', 'yoga']):
            prompt_parts.extend([
                "serene meditation studio",
                "peaceful wellness center interior", 
                "soft ambient lighting",
                "calm zen atmosphere",
                "people in meditation poses",
                "tranquil environment"
            ])
        # Special handling for cooking/culinary events  
        elif any(word in event_text for word in ['cooking', 'chef', 'culinary', 'food', 'recipe']):
            prompt_parts.extend([
                "professional kitchen setting",
                "culinary workshop atmosphere",
                "chef instruction environment"
            ])
        # Special handling for art/creative events
        elif any(word in event_text for word in ['art', 'painting', 'pottery', 'craft', 'creative']):
            prompt_parts.extend([
                "creative art studio",
                "artistic workshop space",
                "creative learning environment"
            ])
        else:
            # Use category-specific styling
            category = event.get('primary_category', 'entertainment')
            category_style = self.category_prompts.get(category, "professional event venue")
            prompt_parts.append(category_style)
        
        # Add venue-specific enhancements
        venue_text = f"{venue_name} {venue_area}".lower()
        for keyword, enhancement in self.venue_keywords.items():
            if keyword in venue_text:
                prompt_parts.append(enhancement)
                break
        
        # Add Dubai context and technical specifications
        prompt_parts.extend([
            "high-quality professional photography",
            "modern Dubai aesthetic", 
            "no text overlay",
            "clean composition"
        ])
        
        # Add appropriate color tone based on event type
        if any(word in event_text for word in ['meditation', 'wellness', 'yoga', 'spa']):
            prompt_parts.append("soft natural lighting, calming colors")
        elif any(word in event_text for word in ['nightlife', 'party', 'club']):
            prompt_parts.append("vibrant colors, dynamic lighting")
        else:
            prompt_parts.append("balanced lighting, professional tones")
        
        final_prompt = ", ".join(prompt_parts)
        
        # Ensure prompt is under DALL-E's limit (1000 characters)
        if len(final_prompt) > 900:
            final_prompt = final_prompt[:900] + "..."
            
        return final_prompt
    
    async def generate_image(self, event: Dict[str, Any]) -> Optional[str]:
        """Generate AI image for a single event"""
        
        event_title = event.get('title', 'Unknown Event')
        logger.info(f"🎨 Generating AI image for: {event_title}")
        
        try:
            # Check cache first
            cache_key = self._create_cache_key(event)
            if cache_key in self.generation_cache:
                logger.info(f"📋 Using cached image for similar event: {event_title}")
                return self.generation_cache[cache_key]
            
            # Create optimized prompt
            prompt = self._create_event_prompt(event)
            logger.debug(f"🎯 Generated prompt: {prompt}")
            
            # Prepare API request
            payload = {
                "model": "dall-e-3",
                "prompt": prompt,
                "size": "1024x1024",
                "quality": "hd",
                "n": 1
            }
            
            # Make API request
            connector = aiohttp.TCPConnector(ssl=False)  # Handle SSL issues
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        image_url = result['data'][0]['url']
                        
                        # Cache the result
                        self.generation_cache[cache_key] = image_url
                        
                        logger.info(f"✅ Successfully generated image for: {event_title}")
                        return image_url
                        
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ DALL-E API error for {event_title}: {response.status} - {error_text}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error(f"⏰ Timeout generating image for: {event_title}")
            return None
        except Exception as e:
            logger.error(f"❌ Error generating image for {event_title}: {str(e)}")
            return None
    
    async def update_event_with_image(self, db, event_id: str, image_url: str) -> bool:
        """Update event in database with generated image"""
        
        try:
            result = await db.events.update_one(
                {"_id": event_id},
                {
                    "$set": {
                        "images.ai_generated": image_url,
                        "images.status": "completed",
                        "images.generated_at": datetime.now().isoformat()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"✅ Updated event {event_id} with AI image")
                return True
            else:
                logger.warning(f"⚠️ No event found with ID {event_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error updating event {event_id} with image: {str(e)}")
            return False
    
    async def process_events_batch(self, db, events: List[Dict[str, Any]], batch_size: int = 5) -> Dict[str, Any]:
        """Process a batch of events for image generation"""
        
        logger.info(f"🎨 Processing batch of {len(events)} events for AI image generation")
        
        results = {
            "total_events": len(events),
            "successful": 0,
            "failed": 0,
            "cached": 0,
            "processing_time": 0
        }
        
        start_time = datetime.now()
        
        # Process events in batches to respect API rate limits
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            logger.info(f"📦 Processing batch {i//batch_size + 1}: events {i+1}-{min(i+batch_size, len(events))}")
            
            # Process batch concurrently
            tasks = []
            for event in batch:
                task = self._process_single_event(db, event)
                tasks.append(task)
            
            # Wait for batch completion
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Update results
            for result in batch_results:
                if isinstance(result, Exception):
                    results["failed"] += 1
                elif result == "cached":
                    results["cached"] += 1
                elif result == "success":
                    results["successful"] += 1
                else:
                    results["failed"] += 1
            
            # Rate limiting delay between batches
            if i + batch_size < len(events):
                logger.info("⏸️ Waiting 10 seconds between batches...")
                await asyncio.sleep(10)
        
        results["processing_time"] = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"🎉 Batch processing complete: {results}")
        return results
    
    async def _process_single_event(self, db, event: Dict[str, Any]) -> str:
        """Process a single event for image generation"""
        
        event_id = event.get('_id')
        if not event_id:
            return "failed"
        
        try:
            # Check if event already has an AI image
            existing_event = await db.events.find_one({"_id": event_id})
            if existing_event and existing_event.get('images', {}).get('ai_generated'):
                logger.debug(f"🔄 Event {event_id} already has AI image, skipping")
                return "cached"
            
            # Generate image
            image_url = await self.generate_image(event)
            
            if image_url:
                # Update event with image
                success = await self.update_event_with_image(db, event_id, image_url)
                return "success" if success else "failed"
            else:
                # Mark as failed
                await db.events.update_one(
                    {"_id": event_id},
                    {
                        "$set": {
                            "images.status": "failed",
                            "images.failed_at": datetime.now().isoformat()
                        }
                    }
                )
                return "failed"
                
        except Exception as e:
            logger.error(f"❌ Error processing event {event_id}: {str(e)}")
            return "failed"

class EventCleanupService:
    """Service to clean up expired events"""
    
    def __init__(self, db):
        self.db = db
        
    async def cleanup_expired_events(self) -> Dict[str, int]:
        """Remove events where end_date < today's date"""
        
        logger.info("🧹 Starting cleanup of expired events...")
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        try:
            # Find expired events
            expired_events = await self.db.events.find({
                "$or": [
                    {"end_date": {"$lt": today.isoformat()}},
                    {"end_date": {"$regex": r"^\d{4}-\d{2}-\d{2}T", "$lt": today.isoformat()}}
                ]
            }).to_list(length=None)
            
            expired_count = len(expired_events)
            
            if expired_count == 0:
                logger.info("✅ No expired events found")
                return {"expired_events_removed": 0}
            
            # Log expired events for audit
            logger.info(f"🗑️ Found {expired_count} expired events to remove:")
            for event in expired_events[:5]:  # Log first 5 for audit
                logger.info(f"  - {event.get('title', 'Unknown')} (ended: {event.get('end_date', 'Unknown')})")
            
            if expired_count > 5:
                logger.info(f"  ... and {expired_count - 5} more events")
            
            # Remove expired events
            result = await self.db.events.delete_many({
                "$or": [
                    {"end_date": {"$lt": today.isoformat()}},
                    {"end_date": {"$regex": r"^\d{4}-\d{2}-\d{2}T", "$lt": today.isoformat()}}
                ]
            })
            
            removed_count = result.deleted_count
            logger.info(f"✅ Successfully removed {removed_count} expired events")
            
            return {"expired_events_removed": removed_count}
            
        except Exception as e:
            logger.error(f"❌ Error during event cleanup: {str(e)}")
            return {"expired_events_removed": 0, "error": str(e)}

# Test functions
async def test_ai_image_generation():
    """Test AI image generation on a few sample events"""
    
    logger.info("🧪 Testing AI Image Generation Service")
    
    # Connect to MongoDB
    mongodb_uri = os.getenv('Mongo_URI')
    if not mongodb_uri:
        logger.error("❌ MongoDB URI not found")
        return
    
    client = AsyncIOMotorClient(mongodb_uri, tlsInsecure=True)
    db = client['DXB']
    
    try:
        # Initialize AI service
        ai_service = AIImageService()
        
        # Get a few sample events for testing
        sample_events = await db.events.find().limit(3).to_list(length=3)
        
        if not sample_events:
            logger.error("❌ No events found in database for testing")
            return
        
        logger.info(f"🎯 Testing with {len(sample_events)} sample events:")
        for event in sample_events:
            logger.info(f"  - {event.get('title', 'Unknown Event')}")
        
        # Test image generation
        results = await ai_service.process_events_batch(db, sample_events, batch_size=2)
        
        logger.info(f"🎉 Test Results: {json.dumps(results, indent=2)}")
        
        # Show generated images
        for event in sample_events:
            updated_event = await db.events.find_one({"_id": event["_id"]})
            ai_image = updated_event.get('images', {}).get('ai_generated')
            if ai_image:
                logger.info(f"✅ Generated image for '{event.get('title')}': {ai_image}")
            else:
                logger.warning(f"❌ No image generated for '{event.get('title')}'")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

async def test_event_cleanup():
    """Test event cleanup functionality"""
    
    logger.info("🧪 Testing Event Cleanup Service")
    
    # Connect to MongoDB
    mongodb_uri = os.getenv('Mongo_URI')
    if not mongodb_uri:
        logger.error("❌ MongoDB URI not found")
        return
    
    client = AsyncIOMotorClient(mongodb_uri, tlsInsecure=True)
    db = client['DXB']
    
    try:
        # Initialize cleanup service
        cleanup_service = EventCleanupService(db)
        
        # Count events before cleanup
        total_events_before = await db.events.count_documents({})
        logger.info(f"📊 Total events before cleanup: {total_events_before}")
        
        # Run cleanup
        results = await cleanup_service.cleanup_expired_events()
        
        # Count events after cleanup
        total_events_after = await db.events.count_documents({})
        logger.info(f"📊 Total events after cleanup: {total_events_after}")
        
        logger.info(f"🎉 Cleanup Results: {json.dumps(results, indent=2)}")
        
    except Exception as e:
        logger.error(f"❌ Cleanup test failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'Mongo.env'))
    
    print("🎨 AI Image Service Testing")
    print("=" * 50)
    
    # Test both services
    asyncio.run(test_ai_image_generation())
    print()
    asyncio.run(test_event_cleanup())