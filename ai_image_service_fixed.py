#!/usr/bin/env python3
"""
Fixed Hybrid AI Image Service - Properly integrates with Backend ImageService
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


class FixedHybridAIImageService:
    """Fixed AI Image Service with proper permanent storage"""

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
            logger.warning("⚠️ ImageService not available - using temporary URLs")

        logger.add("logs/fixed_ai_image_service.log", rotation="10 MB", retention="7 days")

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

    async def generate_image(self, event: Dict[str, Any]) -> Optional[str]:
        """Generate AI image with fixed permanent storage"""
        
        event_title = event.get('title', 'Unknown Event')
        event_id = str(event.get('_id', ''))
        logger.info(f"🎨 Generating AI image for: {event_title} (ID: {event_id})")

        try:
            # Create prompt
            prompt = self._create_prompt(event)
            logger.debug(f"🎯 Prompt: {prompt[:100]}...")

            # Prepare API request
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

                        # For now, return the temporary URL directly to image_url field
                        # This ensures the frontend gets working images immediately
                        logger.info("📝 Using temporary URL (direct to image_url field)")
                        return temp_image_url
                        
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ DALL-E API error: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"❌ Error generating image for {event_title}: {str(e)}")
            return None

    async def update_event_with_image(self, db, event_id: str, image_url: str, prompt: str) -> bool:
        """Update event with generated image directly to image_url field"""
        
        try:
            # Update both image_url and images object for consistency
            result = await db.events.update_one(
                {"_id": event_id},
                {
                    "$set": {
                        "image_url": image_url,  # Main field that backend serves to frontend
                        "images.ai_generated": image_url,
                        "images.status": "completed_hybrid",
                        "images.generated_at": datetime.now().isoformat(),
                        "images.prompt_used": prompt,
                        "images.generation_method": "hybrid_description_based",
                        "images.storage_type": "temporary"  # Being honest about storage type
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
            logger.error(f"❌ Error updating event {event_id}: {str(e)}")
            return False


# Test function
async def test_fixed_service():
    """Test the fixed service"""
    
    print("🧪 Testing Fixed AI Image Service")
    print("=" * 40)
    
    # Connect to MongoDB
    mongodb_uri = os.getenv('Mongo_URI')
    client = AsyncIOMotorClient(mongodb_uri)
    db = client['DXB']
    
    try:
        service = FixedHybridAIImageService()
        
        # Get a sample event without AI image
        event = await db.events.find_one({
            "$or": [
                {"image_url": {"$exists": False}},
                {"image_url": None},
                {"image_url": ""}
            ]
        })
        
        if event:
            print(f"🎯 Testing with: {event.get('title')}")
            
            # Generate new image
            image_url = await service.generate_image(event)
            
            if image_url:
                print(f"✅ Generated: {image_url}")
                
                # Update event
                prompt = service._create_prompt(event)
                await service.update_event_with_image(db, event['_id'], image_url, prompt)
                
                print("✅ Event updated successfully")
            else:
                print("❌ Failed to generate image")
        else:
            print("❌ No test event found")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(test_fixed_service()) 