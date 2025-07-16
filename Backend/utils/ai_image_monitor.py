#!/usr/bin/env python3
"""
AI Image Generation Monitor
Prevents duplicate AI image generation and monitors API usage
"""

import logging
from typing import Dict, Optional, Set
from datetime import datetime, timedelta
import hashlib
import asyncio
from collections import defaultdict

logger = logging.getLogger(__name__)

class AIImageGenerationMonitor:
    """
    Monitor and control AI image generation to prevent duplicates
    """
    
    def __init__(self):
        # Track generated images by event ID
        self.generated_images: Dict[str, str] = {}
        
        # Track generation attempts to prevent rapid retries
        self.generation_attempts: Dict[str, datetime] = {}
        
        # Track API calls for rate limiting
        self.api_calls_per_minute = defaultdict(int)
        
        # Patterns that indicate an AI-generated image
        self.ai_image_patterns = [
            'mydscvr-event-images.s3',
            '/images/events/',
            'oaidalleapiprodscus',
            'openai',
            'dalle',
            '/ai-generated/',
            'cloudfront.net/events/'
        ]
        
        # Maximum API calls per minute
        self.max_api_calls_per_minute = 50
        
        # Minimum time between generation attempts for same event
        self.min_retry_interval = timedelta(hours=24)
        
    def is_ai_generated_image(self, image_url: str) -> bool:
        """Check if an image URL is AI-generated"""
        if not image_url:
            return False
            
        image_url_lower = str(image_url).lower()
        return any(pattern in image_url_lower for pattern in self.ai_image_patterns)
    
    def get_event_image(self, event: Dict) -> Optional[str]:
        """Extract existing AI image from event if present"""
        # Check images.ai_generated first
        if 'images' in event and isinstance(event['images'], dict):
            ai_image = event['images'].get('ai_generated')
            if ai_image and self.is_ai_generated_image(ai_image):
                return ai_image
        
        # Check image_url
        if 'image_url' in event:
            image_url = event.get('image_url')
            if image_url and self.is_ai_generated_image(image_url):
                return image_url
        
        # Check image_urls array
        if 'image_urls' in event and isinstance(event['image_urls'], list):
            for url in event['image_urls']:
                if url and self.is_ai_generated_image(url):
                    return url
        
        return None
    
    def should_generate_image(self, event: Dict) -> bool:
        """
        Determine if an AI image should be generated for this event
        
        Returns:
            bool: True if image should be generated, False otherwise
        """
        event_id = str(event.get('_id', event.get('id', '')))
        
        # Check if event already has an AI image
        existing_image = self.get_event_image(event)
        if existing_image:
            logger.info(f"Event {event_id} already has AI image: {existing_image[:50]}...")
            return False
        
        # Check if we've recently tried to generate for this event
        if event_id in self.generation_attempts:
            last_attempt = self.generation_attempts[event_id]
            time_since_attempt = datetime.now() - last_attempt
            if time_since_attempt < self.min_retry_interval:
                logger.warning(f"Event {event_id} generation attempted {time_since_attempt.total_seconds()/3600:.1f} hours ago, skipping")
                return False
        
        # Check rate limiting
        current_minute = datetime.now().strftime("%Y-%m-%d %H:%M")
        if self.api_calls_per_minute[current_minute] >= self.max_api_calls_per_minute:
            logger.warning(f"Rate limit reached ({self.max_api_calls_per_minute} calls/minute)")
            return False
        
        return True
    
    def record_generation_attempt(self, event_id: str, image_url: Optional[str] = None):
        """Record that we attempted to generate an image"""
        self.generation_attempts[event_id] = datetime.now()
        
        if image_url:
            self.generated_images[event_id] = image_url
        
        # Record API call
        current_minute = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.api_calls_per_minute[current_minute] += 1
    
    async def get_generation_stats(self, db) -> Dict:
        """Get statistics about AI image generation"""
        stats = {
            "timestamp": datetime.now().isoformat(),
            "events_with_ai_images": 0,
            "events_without_ai_images": 0,
            "recent_generation_attempts": len(self.generation_attempts),
            "api_calls_last_minute": 0,
            "cached_images": len(self.generated_images)
        }
        
        # Count events with AI images
        with_ai_images = await db.events.count_documents({
            "$or": [
                {"images.ai_generated": {"$exists": True, "$ne": None, "$ne": ""}},
                {"image_url": {"$regex": "|".join(self.ai_image_patterns), "$options": "i"}}
            ]
        })
        stats["events_with_ai_images"] = with_ai_images
        
        # Count events without AI images
        total_events = await db.events.count_documents({})
        stats["events_without_ai_images"] = total_events - with_ai_images
        
        # Get current API calls
        current_minute = datetime.now().strftime("%Y-%m-%d %H:%M")
        stats["api_calls_last_minute"] = self.api_calls_per_minute.get(current_minute, 0)
        
        return stats
    
    def clear_old_attempts(self):
        """Clear old generation attempts to free memory"""
        cutoff_time = datetime.now() - timedelta(days=7)
        
        # Clear old attempts
        old_attempts = [
            event_id for event_id, attempt_time in self.generation_attempts.items()
            if attempt_time < cutoff_time
        ]
        
        for event_id in old_attempts:
            del self.generation_attempts[event_id]
        
        # Clear old API call records
        current_time = datetime.now()
        old_minutes = [
            minute for minute in self.api_calls_per_minute.keys()
            if datetime.strptime(minute, "%Y-%m-%d %H:%M") < current_time - timedelta(hours=1)
        ]
        
        for minute in old_minutes:
            del self.api_calls_per_minute[minute]


# Global monitor instance
_monitor_instance = None

def get_monitor() -> AIImageGenerationMonitor:
    """Get or create the global monitor instance"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = AIImageGenerationMonitor()
    return _monitor_instance


# Decorator for AI image generation functions
def monitor_ai_generation(func):
    """Decorator to monitor AI image generation"""
    async def wrapper(self, event: Dict, *args, **kwargs):
        monitor = get_monitor()
        event_id = str(event.get('_id', event.get('id', '')))
        
        # Check if we should generate
        if not monitor.should_generate_image(event):
            existing_image = monitor.get_event_image(event)
            if existing_image:
                return existing_image
            return None
        
        # Record attempt
        monitor.record_generation_attempt(event_id)
        
        try:
            # Call the actual generation function
            result = await func(self, event, *args, **kwargs)
            
            # Record successful generation
            if result:
                monitor.record_generation_attempt(event_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"AI generation failed for event {event_id}: {str(e)}")
            raise
    
    return wrapper