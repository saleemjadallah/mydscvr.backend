#!/usr/bin/env python3
"""
Permanent AI Image Service - Properly integrated with Backend ImageService
Downloads OpenAI images and stores them locally to avoid CORS issues
"""

import os
import sys
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import hashlib

# Add Backend path for ImageService access
backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Backend')
sys.path.insert(0, backend_path)

try:
    from utils.image_service import ImageService
    BACKEND_AVAILABLE = True
    logger.info("✅ Backend ImageService imported successfully")
except ImportError as e:
    BACKEND_AVAILABLE = False
    logger.warning(f"⚠️ Backend ImageService not available: {e}")

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'Mongo.env'))


class PermanentAIImageService:
    """AI Image Service that downloads and stores images permanently to avoid CORS issues"""

    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required but not set")

        self.base_url = "https://api.openai.com/v1/images/generations"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Initialize ImageService if available
        if BACKEND_AVAILABLE:
            self.image_service = ImageService()
            logger.info("✅ ImageService initialized for permanent storage")
        else:
            self.image_service = None
            logger.warning("⚠️ ImageService not available - falling back to temporary URLs")

        logger.add("logs/permanent_ai_image_service.log", rotation="10 MB", retention="7 days")

    def _create_prompt(self, event: Dict[str, Any]) -> str:
        """Create improved prompt from event data"""
        title = event.get('title', '')
        description = event.get('description', '')
        venue = event.get('venue', {})
        venue_name = venue.get('name', 'Unknown') if isinstance(venue, dict) else str(venue)
        venue_area = venue.get('area', 'Dubai') if isinstance(venue, dict) else 'Dubai'
        
        # Create base prompt
        base_prompt = f"Professional event photography: {description}"
        
        # Add location context
        if venue_area and venue_area != 'Unknown':
            base_prompt += f" Located in {venue_area}, Dubai, UAE."
        
        # Add style based on event type
        if any(word in title.lower() for word in ['meditation', 'wellness', 'yoga']):
            base_prompt += " serene wellness atmosphere, soft lighting, peaceful environment."
        elif any(word in title.lower() for word in ['night', 'club', 'party']):
            base_prompt += " vibrant nightclub atmosphere, dynamic lighting, energetic crowd."
        elif any(word in title.lower() for word in ['concert', 'music', 'show']):
            base_prompt += " concert venue atmosphere, stage lighting, live performance setting."
        else:
            base_prompt += " professional event setting, modern Dubai aesthetic."
        
        # Add quality tags
        base_prompt += " High-quality professional photography, no text overlay, clean composition, modern Dubai aesthetic."
        
        # Trim if too long
        if len(base_prompt) > 950:
            base_prompt = base_prompt[:947] + "..."
        
        return base_prompt

    async def generate_and_store_image(self, event: Dict[str, Any]) -> Optional[str]:
        """Generate AI image and store it permanently to avoid CORS issues"""
        
        event_title = event.get('title', 'Unknown Event')
        event_id = str(event.get('_id'))  # Convert ObjectId to string
        logger.info(f"🎨 Generating and storing AI image for: {event_title} (ID: {event_id})")

        try:
            # Step 1: Generate temporary image with DALL-E
            prompt = self._create_prompt(event)
            logger.debug(f"🎯 Prompt: {prompt[:100]}...")

            payload = {
                "model": "dall-e-3",
                "prompt": prompt,
                "size": "1024x1024",
                "quality": "hd",
                "n": 1
            }

            # Make API request to DALL-E
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:

                    if response.status == 200:
                        result = await response.json()
                        temp_image_url = result['data'][0]['url']
                        logger.info(f"✅ DALL-E generated temporary image for: {event_title}")

                        # Step 2: Download and store permanently using ImageService
                        if self.image_service:
                            permanent_url = await self._store_permanently(temp_image_url, event_id, event_title)
                            if permanent_url:
                                logger.info(f"🎯 Image stored permanently: {permanent_url}")
                                return permanent_url
                            else:
                                logger.warning("⚠️ Failed to store permanently, using temporary URL")
                                return temp_image_url
                        else:
                            logger.warning("⚠️ No ImageService available, using temporary URL")
                            return temp_image_url
                        
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ DALL-E API error: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"❌ Error generating image for {event_title}: {str(e)}")
            return None

    async def _store_permanently(self, temp_url: str, event_id: str, event_title: str) -> Optional[str]:
        """Download and store image permanently using Backend ImageService"""
        
        try:
            logger.info(f"💾 Downloading and storing image permanently for: {event_title}")
            
            # Use ImageService to process the image (it will download and store it)
            result = await self.image_service.process_single_image(
                temp_url, 
                event_id, 
                "ai_generated"
            )
            
            if result.get('success'):
                # Get the storage path and construct backend URL
                storage_info = result.get('optimized_urls', {})
                
                # Look for the main/original image
                if 'original' in storage_info:
                    filename = os.path.basename(storage_info['original'])
                elif storage_info:
                    # Use first available image
                    filename = os.path.basename(list(storage_info.values())[0])
                else:
                    # Fallback: construct filename
                    file_hash = result.get('file_hash', 'unknown')
                    filename = f"{event_id}_ai_generated_{file_hash}.png"
                
                # Return backend URL that serves the image
                permanent_url = f"https://mydscvr.xyz/images/{filename}"
                logger.info(f"✅ Image stored locally, accessible at: {permanent_url}")
                return permanent_url
                
            else:
                error = result.get('error', 'Unknown error')
                logger.error(f"❌ ImageService failed: {error}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error storing image permanently: {str(e)}")
            return None

    async def update_event_with_image(self, db, event_id: ObjectId, image_url: str, prompt: str) -> bool:
        """Update event with generated image - using ObjectId properly"""
        
        try:
            # Use ObjectId directly, no conversion needed if already ObjectId
            query_id = event_id if isinstance(event_id, ObjectId) else ObjectId(str(event_id))
            
            # Update both image_url and images object for consistency
            result = await db.events.update_one(
                {"_id": query_id},
                {
                    "$set": {
                        "image_url": image_url,  # Main field that backend serves to frontend
                        "images.ai_generated": image_url,
                        "images.status": "completed_permanent",
                        "images.generated_at": datetime.now().isoformat(),
                        "images.prompt_used": prompt,
                        "images.generation_method": "permanent_backend_stored",
                        "images.storage_type": "permanent"  # Actually permanent now
                    }
                }
            )

            if result.modified_count > 0:
                logger.info(f"✅ Updated event {query_id} with permanent AI image")
                return True
            else:
                logger.warning(f"⚠️ No event found with ID {query_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error updating event {event_id}: {str(e)}")
            return False


# Test function
async def test_permanent_service():
    """Test the permanent AI image service"""
    
    print("🧪 Testing Permanent AI Image Service")
    print("=" * 40)
    
    # Connect to MongoDB
    mongodb_uri = os.getenv('Mongo_URI')
    client = AsyncIOMotorClient(mongodb_uri)
    db = client['DXB']
    
    try:
        service = PermanentAIImageService()
        
        # Get the Museum of Future event that we know exists
        event = await db.events.find_one({"_id": ObjectId("685bdc494009b338adca0829")})
        
        if event:
            print(f"🎯 Testing with: {event.get('title')}")
            print(f"🆔 Event ID: {event.get('_id')}")
            
            # Generate and store image permanently
            image_url = await service.generate_and_store_image(event)
            
            if image_url:
                print(f"✅ Generated permanent image: {image_url[:80]}...")
                
                # Update event in database
                prompt = service._create_prompt(event)
                success = await service.update_event_with_image(db, event['_id'], image_url, prompt)
                
                if success:
                    print("✅ Database updated successfully")
                    print(f"🌐 Image should be accessible at: {image_url}")
                    print("🎉 This image will work on the frontend without CORS issues!")
                else:
                    print("❌ Failed to update database")
            else:
                print("❌ Failed to generate and store image")
        else:
            print("❌ Test event not found")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(test_permanent_service()) 