#!/usr/bin/env python3
"""
Hybrid AI Image Service - Uses Description-Based Prompts with Smart Enhancements
Combines event descriptions with contextual improvements for best results
Enhanced with permanent image storage via Backend ImageService
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
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'AI_API.env'))


class HybridAIImageService:
    """
    Hybrid AI Image Service that uses event descriptions as primary prompts
    with smart enhancements for better image quality and consistency
    Enhanced with permanent storage via Backend ImageService
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

        # Initialize ImageService if available
        if BACKEND_AVAILABLE:
            self.image_service = ImageService()
            logger.info("✅ ImageService initialized for permanent storage")
        else:
            self.image_service = None
            logger.warning("⚠️ ImageService not available - using temporary URLs")

        # Configure logging
        logger.add("logs/hybrid_ai_image_service.log", rotation="10 MB", retention="7 days")

        # Image generation cache
        self.generation_cache = {}

        # Dubai venue enhancements for better context
        self.dubai_venues = {
            "burj khalifa": "iconic Burj Khalifa backdrop, luxury Dubai setting",
            "burj al arab": "iconic sail-shaped Burj Al Arab hotel, luxury beachfront",
            "dubai marina": "Dubai Marina waterfront, modern skyscrapers, marina views",
            "downtown dubai": "Downtown Dubai, urban sophistication, modern architecture",
            "jumeirah": "Jumeirah beachfront, coastal Dubai, luxury resort atmosphere",
            "dubai mall": "Dubai Mall, world's largest shopping destination",
            "coca-cola arena": "state-of-the-art arena, modern concert venue",
            "dubai world trade centre": "professional conference venue, business district",
            "la mer": "beachfront lifestyle destination, contemporary architecture",
            "bluewaters": "Ain Dubai backdrop, waterfront entertainment district",
            "city walk": "urban outdoor lifestyle destination, modern retail",
            "jbr": "Jumeirah Beach Residence, beachfront towers, The Walk promenade"
        }

        # Style enhancers based on event type detection
        self.style_enhancers = {
            'nightlife': "vibrant nightclub atmosphere, dynamic lighting, energetic crowd",
            'meditation': "serene wellness center, soft ambient lighting, peaceful atmosphere",
            'concert': "concert venue with stage lighting, live performance atmosphere",
            'dining': "elegant restaurant setting, fine dining ambiance",
            'market': "bustling market atmosphere, artisan displays, community gathering",
            'festival': "festive outdoor setting, celebration atmosphere, colorful decorations",
            'business': "professional conference setting, modern business environment",
            'family': "family-friendly venue, welcoming atmosphere for all ages",
            'art': "contemporary gallery space, artistic exhibition setting",
            'fitness': "modern fitness facility, wellness atmosphere"
        }

    def _create_cache_key(self, event: Dict[str, Any]) -> str:
        """Create cache key based on description hash"""
        description = event.get('description', '')
        title = event.get('title', '')
        key_string = f"{title}_{description}"
        return hashlib.md5(key_string.encode()).hexdigest()[:12]

    def _analyze_description_quality(self, description: str) -> Dict[str, Any]:
        """Analyze description quality for prompt generation"""

        quality = {
            'score': 10,
            'length': len(description),
            'has_venue_details': False,
            'has_atmosphere': False,
            'has_dubai_context': False,
            'has_visual_words': False,
            'needs_enhancement': False
        }

        # Length check
        if len(description) < 50:
            quality['score'] -= 3
            quality['needs_enhancement'] = True

        # Content checks
        venue_words = ['venue', 'location', 'setting', 'space', 'center', 'hall', 'arena',
                       'theatre', 'club', 'restaurant']
        quality['has_venue_details'] = any(word in description.lower() for word in venue_words)

        atmosphere_words = ['atmosphere', 'ambiance', 'environment', 'experience', 'vibe', 'mood']
        quality['has_atmosphere'] = any(word in description.lower() for word in atmosphere_words)

        quality['has_dubai_context'] = 'dubai' in description.lower()

        visual_words = ['beautiful', 'stunning', 'elegant', 'vibrant', 'modern', 'traditional',
                        'spectacular', 'intimate']
        quality['has_visual_words'] = any(word in description.lower() for word in visual_words)

        # Reduce score for missing elements
        if not quality['has_venue_details']:
            quality['score'] -= 2
        if not quality['has_atmosphere']:
            quality['score'] -= 1
        if not quality['has_dubai_context']:
            quality['score'] -= 1
        if not quality['has_visual_words']:
            quality['score'] -= 1

        quality['needs_enhancement'] = quality['score'] < 7

        return quality

    def _detect_event_type(self, title: str, description: str) -> str:
        """Detect event type from title and description"""

        text = f"{title} {description}".lower()

        # Define detection patterns
        patterns = {
            'meditation': ['meditation', 'breathwork', 'mindfulness', 'zen', 'yoga', 'wellness'],
            'nightlife': ['nightlife', 'club', 'party', 'ladies night', 'dj', 'drinks', 'bar'],
            'concert': ['concert', 'live music', 'singer', 'band', 'performance', 'show'],
            'dining': ['restaurant', 'dining', 'brunch', 'dinner', 'culinary', 'food'],
            'market': ['market', 'artisan', 'craft', 'handmade', 'makers', 'vendors'],
            'festival': ['festival', 'celebration', 'fair', 'carnival', 'fiesta'],
            'business': ['conference', 'seminar', 'workshop', 'networking', 'professional'],
            'family': ['family', 'kids', 'children', 'play', 'family-friendly'],
            'art': ['art', 'gallery', 'exhibition', 'museum', 'creative'],
            'fitness': ['fitness', 'gym', 'workout', 'sports', 'training']
        }

        for event_type, keywords in patterns.items():
            if any(keyword in text for keyword in keywords):
                return event_type

        return 'general'

    def _enhance_venue_context(self, description: str) -> str:
        """Add Dubai venue context if recognized venue is mentioned"""

        enhanced_desc = description

        for venue, enhancement in self.dubai_venues.items():
            if venue in description.lower():
                enhanced_desc += f" {enhancement}."
                break

        return enhanced_desc

    def _create_hybrid_prompt(self, event: Dict[str, Any]) -> str:
        """Create hybrid prompt using description + smart enhancements"""

        title = event.get('title', '')
        description = event.get('description', '')
        venue_name = event.get('venue', {}).get('name', '')
        venue_area = event.get('venue', {}).get('area', '')

        # Analyze description quality
        quality = self._analyze_description_quality(description)

        # Start with description-based approach
        if quality['score'] >= 6 and len(description) >= 40:
            # Use description as primary prompt
            base_prompt = f"Professional event photography: {description}"

            # Enhance with venue context
            base_prompt = self._enhance_venue_context(base_prompt)

            # Add Dubai context if missing
            if not quality['has_dubai_context']:
                if venue_area:
                    base_prompt += f" Located in {venue_area}, Dubai, UAE."
                else:
                    base_prompt += " Located in Dubai, UAE."

            # Add venue name if available and not in description
            if venue_name and venue_name.lower() not in description.lower():
                base_prompt += f" Venue: {venue_name}."

            # Detect event type and add style enhancement
            event_type = self._detect_event_type(title, description)
            if event_type in self.style_enhancers:
                style_enhancement = self.style_enhancers[event_type]
                base_prompt += f" {style_enhancement}."

            # Add photography specifications
            photography_specs = " High-quality professional photography, no text overlay, "
            photography_specs += "clean composition, modern Dubai aesthetic."
            base_prompt += photography_specs

        else:
            # Fallback to enhanced category-based approach for poor descriptions
            logger.info(f"Using fallback approach for event: {title} (quality score: {quality['score']})")

            base_prompt = f"Professional event photography in Dubai: {title}"

            if venue_name:
                base_prompt += f" at {venue_name}"
            if venue_area:
                base_prompt += f" in {venue_area}"

            # Use description if available, even if short
            if description:
                base_prompt += f". {description}"

            # Add category-based enhancement
            event_type = self._detect_event_type(title, description)
            if event_type in self.style_enhancers:
                base_prompt += f" {self.style_enhancers[event_type]}."

            base_prompt += " High-quality professional photography, modern Dubai aesthetic, no text overlay."

        # Ensure prompt is within DALL-E's limit
        if len(base_prompt) > 950:
            base_prompt = base_prompt[:947] + "..."

        return base_prompt

    async def generate_image(self, event: Dict[str, Any]) -> Optional[str]:
        """Generate AI image using hybrid approach with permanent storage"""

        event_title = event.get('title', 'Unknown Event')
        event_id = str(event.get('_id', ''))
        logger.info(f"🎨 Generating hybrid AI image for: {event_title} (ID: {event_id})")

        try:
            # Check cache first
            cache_key = self._create_cache_key(event)
            if cache_key in self.generation_cache:
                logger.info(f"📋 Using cached image for: {event_title}")
                return self.generation_cache[cache_key]

            # Create hybrid prompt
            prompt = self._create_hybrid_prompt(event)
            logger.debug(f"🎯 Hybrid prompt: {prompt}")

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
                        logger.debug(f"🔗 Temporary URL: {temp_image_url}")

                        # Store image permanently if ImageService is available
                        if self.image_service and event_id:
                            try:
                                # Download and store the image permanently
                                permanent_url = await self._store_image_permanently(
                                    temp_image_url, event_id, event_title
                                )

                                if permanent_url:
                                    # Cache and return permanent URL
                                    self.generation_cache[cache_key] = permanent_url
                                    logger.info(f"🎯 Permanent image stored: {permanent_url}")
                                    return permanent_url
                                else:
                                    logger.warning("⚠️ Failed to store permanently, using temporary URL")
                                    # Fall back to temporary URL
                                    self.generation_cache[cache_key] = temp_image_url
                                    return temp_image_url

                            except Exception as e:
                                logger.error(f"❌ Error storing image permanently: {str(e)}")
                                # Fall back to temporary URL
                                self.generation_cache[cache_key] = temp_image_url
                                return temp_image_url
                        else:
                            # No ImageService available or no event ID - use temporary URL
                            self.generation_cache[cache_key] = temp_image_url
                            logger.info("📝 Using temporary URL (no permanent storage)")
                            return temp_image_url

                    else:
                        error_text = await response.text()
                        logger.error(f"❌ DALL-E API error for {event_title}: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"❌ Error generating hybrid image for {event_title}: {str(e)}")
            return None

    async def _store_image_permanently(self, temp_url: str, event_id: str, event_title: str) -> Optional[str]:
        """Download image from temporary URL and store permanently using ImageService"""

        try:
            logger.info(f"💾 Storing image permanently for event: {event_title}")

            # Download image from temporary URL
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(temp_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        logger.info(f"📥 Downloaded image data ({len(image_data)} bytes)")

                        # Create filename with event ID
                        filename = f"{event_id}_ai_generated_{hashlib.md5(temp_url.encode()).hexdigest()[:8]}.jpg"

                        # Store using ImageService
                        stored_path = await self.image_service.process_single_image(
                            image_data, filename
                        )

                        if stored_path:
                            # Create permanent URL
                            # Assuming the backend serves images at /images/ endpoint
                            permanent_url = f"https://api.mydscvr.ai/images/{filename}"
                            logger.info(f"✅ Image stored permanently: {stored_path}")
                            logger.info(f"🔗 Permanent URL: {permanent_url}")
                            return permanent_url
                        else:
                            logger.error("❌ ImageService failed to store image")
                            return None
                    else:
                        logger.error(f"❌ Failed to download image: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"❌ Error storing image permanently: {str(e)}")
            return None

    async def update_event_with_image(self, db, event_id: str, image_url: str, prompt: str) -> bool:
        """Update event with generated image and prompt used"""

        try:
            result = await db.events.update_one(
                {"_id": event_id},
                {
                    "$set": {
                        "images.ai_generated": image_url,
                        "images.status": "completed_hybrid",
                        "images.generated_at": datetime.now().isoformat(),
                        "images.prompt_used": prompt,
                        "images.generation_method": "hybrid_description_based",
                        "images.storage_type": "permanent" if self.image_service else "temporary"
                    }
                }
            )

            if result.modified_count > 0:
                logger.info(f"✅ Updated event {event_id} with hybrid AI image")
                return True
            else:
                logger.warning(f"⚠️ No event found with ID {event_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error updating event {event_id} with image: {str(e)}")
            return False


# Test the hybrid approach
async def test_hybrid_approach():
    """Test the hybrid AI image service"""

    print("🔬 Testing Hybrid AI Image Service")
    print("=" * 50)

    # Connect to MongoDB
    mongodb_uri = os.getenv('Mongo_URI')
    client = AsyncIOMotorClient(mongodb_uri, tlsInsecure=True)
    db = client['DXB']

    try:
        # Initialize hybrid service
        hybrid_service = HybridAIImageService()

        # Test with the meditation event to see improvement
        meditation_event = await db.events.find_one({'title': 'ToDA - 9D Breathwork Meditation'})

        if meditation_event:
            print(f"🧘 Testing with: {meditation_event.get('title')}")
            print(f"📝 Description: {meditation_event.get('description')}")

            # Generate hybrid prompt
            hybrid_prompt = hybrid_service._create_hybrid_prompt(meditation_event)
            print("\n🎯 Hybrid Prompt:")
            print(f"   {hybrid_prompt}")

            # Generate image
            print("\n🎨 Generating image with hybrid approach...")
            image_url = await hybrid_service.generate_image(meditation_event)

            if image_url:
                print(f"✅ Generated: {image_url}")

                # Update in database
                await hybrid_service.update_event_with_image(
                    db, meditation_event['_id'], image_url, hybrid_prompt
                )
            else:
                print("❌ Failed to generate image")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        client.close()


if __name__ == "__main__":
    # Load environment
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'Mongo.env'))
    asyncio.run(test_hybrid_approach())
