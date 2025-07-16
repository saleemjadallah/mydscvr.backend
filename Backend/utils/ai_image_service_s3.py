"""
AI Image Service with S3 Integration
Generates AI images and stores them directly in S3
"""

import os
import asyncio
import aiohttp
import hashlib
from typing import Optional, Dict, List
from datetime import datetime
import logging
from openai import AsyncOpenAI
import backoff

from .s3_image_service import S3ImageService
from .ai_image_monitor import monitor_ai_generation, get_monitor
from config import settings

logger = logging.getLogger(__name__)

class AIImageServiceS3:
    def __init__(self, openai_api_key: str, s3_service: S3ImageService):
        """
        Initialize AI Image Service with S3 storage
        
        Args:
            openai_api_key: OpenAI API key
            s3_service: Initialized S3ImageService instance
        """
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.s3_service = s3_service
        self.batch_size = 5  # Process 5 images concurrently
        
    @monitor_ai_generation
    async def generate_event_image(self, event: Dict) -> Optional[str]:
        """
        Generate AI image for an event and store in S3
        
        Args:
            event: Event document from MongoDB
            
        Returns:
            S3 URL of the generated image or None if failed
        """
        try:
            # Check if event already has an AI-generated image
            existing_ai_image = None
            if 'images' in event and isinstance(event['images'], dict):
                existing_ai_image = event['images'].get('ai_generated')
            elif 'image_url' in event:
                # Check if image_url is an AI-generated image (from S3 or local)
                image_url = event.get('image_url', '')
                if any(pattern in str(image_url) for pattern in ['mydscvr-event-images.s3', '/images/events/', 'oaidalleapiprodscus']):
                    existing_ai_image = image_url
                    
            # If event already has an AI image, return it without regenerating
            if existing_ai_image and existing_ai_image not in [None, '', 'null']:
                logger.info(f"Event {event.get('_id')} already has AI-generated image: {existing_ai_image[:50]}...")
                return existing_ai_image
            
            # Check if image already exists for this event
            event_id = str(event.get('_id', event.get('id', '')))
            event_name = event.get('name', 'Untitled Event')
            
            # Create a deterministic filename based on event
            filename = self._generate_filename(event_id, event_name)
            
            # Check if already exists in S3
            s3_key = f"events/{filename}"
            existing_url = self._check_s3_exists(s3_key)
            if existing_url:
                logger.info(f"Image already exists in S3 for event {event_id}")
                return existing_url
            
            # Generate prompt
            prompt = self._create_prompt(event)
            
            # Generate image with DALL-E 3
            logger.info(f"Generating AI image for event: {event_name}")
            image_url = await self._generate_with_dalle3(prompt)
            
            if not image_url:
                return None
            
            # Download and upload to S3
            image_data = await self._download_image(image_url)
            if image_data:
                s3_url = self.s3_service.upload_image_from_bytes(
                    image_data,
                    filename,
                    content_type='image/jpeg'
                )
                logger.info(f"Successfully uploaded AI image to S3: {s3_url}")
                return s3_url
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate AI image for event {event.get('name')}: {str(e)}")
            return None
    
    def _generate_filename(self, event_id: str, event_name: str) -> str:
        """Generate a consistent filename for the event"""
        # Clean event name
        clean_name = event_name.replace(' ', '_')[:50]
        clean_name = ''.join(c for c in clean_name if c.isalnum() or c == '_')
        
        # Create hash for uniqueness
        hash_str = hashlib.md5(f"{event_id}_{event_name}".encode()).hexdigest()[:8]
        
        return f"{event_id}_{clean_name}_{hash_str}.jpg"
    
    def _check_s3_exists(self, s3_key: str) -> Optional[str]:
        """Check if image already exists in S3"""
        try:
            # Try to get object metadata
            self.s3_service.s3_client.head_object(
                Bucket=self.s3_service.bucket_name,
                Key=s3_key
            )
            return f"{self.s3_service.cdn_url}/{s3_key}"
        except:
            return None
    
    def _create_prompt(self, event: Dict) -> str:
        """Create an optimized prompt for DALL-E 3"""
        name = event.get('name', 'Event')
        description = event.get('description', '')[:200]
        venue = event.get('venue', {}).get('name', '')
        category = event.get('category', 'General')
        
        # Build contextual prompt
        prompt_parts = [
            f"Professional event promotional image for '{name}'",
            f"Category: {category}"
        ]
        
        if venue:
            prompt_parts.append(f"Venue: {venue}")
        
        if description:
            # Extract key themes from description
            prompt_parts.append(f"Theme: {description[:100]}")
        
        # Add style guidelines
        prompt_parts.extend([
            "Style: Modern, vibrant, high-quality photography",
            "Mood: Exciting, inviting, professional",
            "No text or logos in the image"
        ])
        
        return ". ".join(prompt_parts)
    
    @backoff.on_exception(
        backoff.expo,
        Exception,
        max_tries=3,
        max_time=30
    )
    async def _generate_with_dalle3(self, prompt: str) -> Optional[str]:
        """Generate image using DALL-E 3 with retry logic"""
        try:
            response = await self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1
            )
            
            if response.data and len(response.data) > 0:
                return response.data[0].url
            
            return None
            
        except Exception as e:
            logger.error(f"DALL-E 3 generation failed: {str(e)}")
            raise
    
    async def _download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.error(f"Failed to download image: HTTP {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Failed to download image: {str(e)}")
            return None
    
    async def process_events_batch(self, events: List[Dict]) -> Dict[str, str]:
        """
        Process a batch of events to generate AI images
        
        Args:
            events: List of event documents
            
        Returns:
            Dictionary mapping event IDs to S3 image URLs
        """
        results = {}
        
        # Process in smaller batches to avoid rate limits
        for i in range(0, len(events), self.batch_size):
            batch = events[i:i + self.batch_size]
            
            # Create tasks for concurrent processing
            tasks = []
            for event in batch:
                task = self.generate_event_image(event)
                tasks.append(task)
            
            # Wait for batch to complete
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect results
            for event, result in zip(batch, batch_results):
                event_id = str(event.get('_id', event.get('id', '')))
                if isinstance(result, str):
                    results[event_id] = result
                elif isinstance(result, Exception):
                    logger.error(f"Failed to process event {event_id}: {result}")
                    results[event_id] = None
                else:
                    results[event_id] = result
            
            # Small delay between batches to respect rate limits
            if i + self.batch_size < len(events):
                await asyncio.sleep(2)
        
        return results


# Factory function to create S3-enabled AI image service
def create_ai_image_service_s3():
    """Create AI image service with S3 storage"""
    
    # Get configuration
    openai_key = getattr(settings, 'openai_api_key', None)
    if not openai_key:
        raise ValueError("OPENAI_API_KEY not configured")
    
    # Create S3 service
    s3_bucket = getattr(settings, 's3_image_bucket', 'mydscvr-event-images')
    s3_region = getattr(settings, 's3_region', 'us-east-1')
    aws_access_key = getattr(settings, 'aws_access_key_id', None)
    aws_secret_key = getattr(settings, 'aws_secret_access_key', None)
    
    s3_service = S3ImageService(
        bucket_name=s3_bucket,
        region=s3_region,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
    
    return AIImageServiceS3(openai_key, s3_service)