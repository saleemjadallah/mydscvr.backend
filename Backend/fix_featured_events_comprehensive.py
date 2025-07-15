#!/usr/bin/env python3
"""
COMPREHENSIVE FEATURED EVENTS FIX SCRIPT
Fixes the issue where featured events don't have proper images

PROBLEM ANALYSIS:
1. Events with good images should be is_featured=True
2. Events with placeholder/broken images should be is_featured=False  
3. Many events are pointing to wrong duplicate images
4. Some events have expired OpenAI URLs
5. Some events still have old Unsplash hiking image URLs

SOLUTION:
1. Identify events with good vs bad images
2. Set is_featured=True for events with real images
3. Set is_featured=False for events with placeholder/broken images
4. Fix broken image URLs where possible
5. Update the frontend's default image logic

Created: January 2025
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
import re

# Add the parent directory to the path so we can import from the backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Settings
settings = Settings()

class FeaturedEventsFixService:
    def __init__(self):
        self.client = None
        self.db = None
        self.events_collection = None
        
    async def connect_to_database(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(settings.mongodb_url)
            self.db = self.client.DXB
            self.events_collection = self.db.events
            print("✅ Connected to MongoDB successfully")
        except Exception as e:
            print(f"❌ Failed to connect to MongoDB: {e}")
            return False
        return True
    
    def is_good_image_url(self, url: str) -> bool:
        """
        Determine if an image URL is good (real image) or bad (placeholder/broken)
        """
        if not url or url.strip() == "":
            return False
            
        # Bad URLs (placeholders, expired, generic)
        bad_patterns = [
            # Old placeholder URLs
            "https://images.unsplash.com/photo-1551632811-561732d1e306",  # Hiking image
            "assets/images/mydscvr-logo.png",  # Logo placeholder
            
            # Expired OpenAI URLs (these expire after 24 hours)
            "oaidalleapiprodscus.blob.core.windows.net",
            
            # Generic placeholders
            "placeholder",
            "default",
            "no-image",
            "missing",
        ]
        
        for pattern in bad_patterns:
            if pattern in url.lower():
                return False
        
        # Good URLs should point to mydscvr.xyz/images/ with specific image files
        if "mydscvr.xyz/images/" in url and url.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            # Make sure it's not a duplicate wrong assignment
            if "685bdec34009b338adca0853_Dubai_Miracle_Garden_and_Glow_Garden_Tour_2025_bd980e4f.jpg" in url:
                return False  # This is the wrong duplicate image
            return True
            
        return False
    
    async def analyze_events_images(self):
        """Analyze all events and categorize their images"""
        print("🔍 Analyzing events and their images...")
        
        all_events = []
        async for event in self.events_collection.find({}):
            all_events.append(event)
        
        print(f"📊 Found {len(all_events)} total events")
        
        # Categorize events
        events_with_good_images = []
        events_with_bad_images = []
        events_needing_image_fix = []
        
        for event in all_events:
            event_id = str(event.get('_id'))
            title = event.get('title', 'Untitled')
            image_url = event.get('image_url', '')
            ai_generated = event.get('images', {}).get('ai_generated', '')
            is_featured = event.get('is_featured', False)
            
            # Check best available image
            best_image = ai_generated if ai_generated else image_url
            
            if self.is_good_image_url(best_image):
                events_with_good_images.append({
                    'id': event_id,
                    'title': title,
                    'image_url': image_url,
                    'ai_generated': ai_generated,
                    'best_image': best_image,
                    'current_featured': is_featured
                })
            else:
                events_with_bad_images.append({
                    'id': event_id,
                    'title': title,
                    'image_url': image_url,
                    'ai_generated': ai_generated,
                    'best_image': best_image,
                    'current_featured': is_featured
                })
                
                # Check if we can fix the image by finding original
                if event.get('_id'):
                    events_needing_image_fix.append(event)
        
        print(f"✅ Events with GOOD images: {len(events_with_good_images)}")
        print(f"❌ Events with BAD images: {len(events_with_bad_images)}")
        print(f"🔧 Events needing image fix: {len(events_needing_image_fix)}")
        
        return events_with_good_images, events_with_bad_images, events_needing_image_fix
    
    async def fix_featured_status(self, events_with_good_images, events_with_bad_images):
        """Fix the is_featured status based on image quality"""
        print("🎯 Fixing featured status...")
        
        # Convert string IDs to ObjectId format for MongoDB query
        from bson import ObjectId
        
        # Set is_featured=True for events with good images
        good_event_ids = [ObjectId(event['id']) for event in events_with_good_images]
        if good_event_ids:
            result = await self.events_collection.update_many(
                {'_id': {'$in': good_event_ids}},
                {'$set': {'is_featured': True}}
            )
            print(f"✅ Set {result.modified_count} events with good images to featured=True")
        
        # Set is_featured=False for events with bad images  
        bad_event_ids = [ObjectId(event['id']) for event in events_with_bad_images]
        if bad_event_ids:
            result = await self.events_collection.update_many(
                {'_id': {'$in': bad_event_ids}},
                {'$set': {'is_featured': False}}
            )
            print(f"❌ Set {result.modified_count} events with bad images to featured=False")
    
    async def fix_broken_image_urls(self, events_needing_fix):
        """Try to fix broken image URLs where possible"""
        print("🔧 Fixing broken image URLs...")
        
        fixed_count = 0
        for event in events_needing_fix[:50]:  # Limit to first 50 to avoid overwhelming
            event_id = str(event['_id'])
            title = event.get('title', '')
            
            # Try to construct a proper image URL based on event ID and title
            # This follows the pattern we've seen in good URLs
            if event_id and title:
                # Clean the title for URL
                clean_title = re.sub(r'[^\w\s-]', '', title).strip()
                clean_title = re.sub(r'[-\s]+', '_', clean_title)
                
                # Generate a potential image URL
                potential_url = f"https://mydscvr.xyz/images/{event_id}_{clean_title}_generated.jpg"
                
                # Update the event (we'll let the frontend handle fallbacks)
                await self.events_collection.update_one(
                    {'_id': event['_id']},
                    {
                        '$set': {
                            'image_url': potential_url,
                            'images.ai_generated': potential_url,
                            'images.status': 'url_reconstructed',
                            'is_featured': False  # Keep as non-featured until we verify image exists
                        }
                    }
                )
                fixed_count += 1
        
        print(f"🔧 Attempted to fix {fixed_count} broken image URLs")
    
    async def update_placeholder_urls(self):
        """Update old placeholder URLs to use the new logo system"""
        print("🖼️ Updating placeholder image URLs...")
        
        # Update old Unsplash hiking URLs
        result1 = await self.events_collection.update_many(
            {'image_url': 'https://images.unsplash.com/photo-1551632811-561732d1e306?ixlib=rb-4.0.3&auto=format&fit=crop&w=2070&q=80'},
            {
                '$set': {
                    'image_url': 'assets/images/mydscvr-logo.png',
                    'is_featured': False
                }
            }
        )
        print(f"📷 Updated {result1.modified_count} events from old Unsplash URL to logo")
        
        # Update expired OpenAI URLs
        result2 = await self.events_collection.update_many(
            {'images.ai_generated': {'$regex': 'oaidalleapiprodscus.blob.core.windows.net'}},
            {
                '$unset': {'images.ai_generated': ''},
                '$set': {
                    'image_url': 'assets/images/mydscvr-logo.png',
                    'images.status': 'openai_expired',
                    'is_featured': False
                }
            }
        )
        print(f"⏰ Updated {result2.modified_count} events with expired OpenAI URLs")
    
    async def generate_report(self):
        """Generate a final report"""
        print("\n📈 FINAL REPORT:")
        print("=" * 50)
        
        # Count featured vs non-featured
        featured_count = await self.events_collection.count_documents({'is_featured': True})
        non_featured_count = await self.events_collection.count_documents({'is_featured': False})
        total_count = await self.events_collection.count_documents({})
        
        print(f"📊 Total Events: {total_count}")
        print(f"⭐ Featured Events: {featured_count}")
        print(f"📝 Non-Featured Events: {non_featured_count}")
        print(f"📱 Featured Percentage: {(featured_count/total_count)*100:.1f}%")
        
        # Sample some featured events
        print(f"\n🎯 Sample Featured Events (with good images):")
        async for event in self.events_collection.find(
            {'is_featured': True},
            {'title': 1, 'image_url': 1, 'images.ai_generated': 1}
        ).limit(5):
            title = event.get('title', 'Untitled')[:50]
            image_url = event.get('image_url', '')[:80]
            print(f"   ✅ {title} -> {image_url}")
            
        print(f"\n📝 Sample Non-Featured Events (with placeholders):")
        async for event in self.events_collection.find(
            {'is_featured': False},
            {'title': 1, 'image_url': 1}
        ).limit(5):
            title = event.get('title', 'Untitled')[:50]
            image_url = event.get('image_url', '')[:80] 
            print(f"   ❌ {title} -> {image_url}")
    
    async def run_comprehensive_fix(self):
        """Run the complete featured events fix"""
        print("🚀 Starting Comprehensive Featured Events Fix")
        print("=" * 60)
        
        if not await self.connect_to_database():
            return False
        
        try:
            # Step 1: Analyze current state
            events_with_good_images, events_with_bad_images, events_needing_fix = await self.analyze_events_images()
            
            # Step 2: Fix featured status
            await self.fix_featured_status(events_with_good_images, events_with_bad_images)
            
            # Step 3: Update placeholder URLs
            await self.update_placeholder_urls()
            
            # Step 4: Try to fix some broken URLs (limited to avoid overwhelming)
            # await self.fix_broken_image_urls(events_needing_fix)
            
            # Step 5: Generate final report
            await self.generate_report()
            
            print("\n🎉 Comprehensive Featured Events Fix Complete!")
            return True
            
        except Exception as e:
            print(f"❌ Error during fix: {e}")
            return False
        finally:
            if self.client:
                self.client.close()

async def main():
    service = FeaturedEventsFixService()
    success = await service.run_comprehensive_fix()
    if success:
        print("\n✅ All fixes applied successfully!")
        print("💡 Next steps:")
        print("   1. Deploy the frontend with updated logo placeholders")
        print("   2. Verify featured events display properly")
        print("   3. Monitor image loading in production")
    else:
        print("\n❌ Fix process failed!")

if __name__ == "__main__":
    asyncio.run(main()) 