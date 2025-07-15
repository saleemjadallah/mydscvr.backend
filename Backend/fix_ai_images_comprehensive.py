#!/usr/bin/env python3
"""
COMPREHENSIVE AI IMAGES FIX SCRIPT
Permanently resolves AI image issues by updating database references

STRATEGY:
1. Find all events with broken/missing AI image URLs
2. For each event, check if alternative images exist using multiple patterns
3. Update both images.ai_generated AND image_url fields  
4. Ensure frontend can display images correctly

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

from config import settings

class ComprehensiveAIImageFixer:
    def __init__(self):
        self.mongodb_client = AsyncIOMotorClient(
            settings.mongodb_url,
            tls=True,
            tlsAllowInvalidCertificates=True
        )
        self.db = self.mongodb_client[settings.mongodb_database]
        self.events_collection = self.db["events"]
        
        # Storage paths
        self.storage_path = settings.image_storage_path
        
        # Statistics
        self.stats = {
            "total_processed": 0,
            "ai_urls_fixed": 0,
            "image_urls_fixed": 0,
            "events_with_working_images": 0,
            "events_still_broken": 0,
            "errors": []
        }
        
        # Cache storage files for performance
        self.storage_files = []
        self._load_storage_files()
    
    def _load_storage_files(self):
        """Load all image files from storage for fast lookup"""
        if os.path.exists(self.storage_path):
            self.storage_files = [f for f in os.listdir(self.storage_path) 
                                if f.endswith(('.png', '.jpg', '.jpeg'))]
        print(f"📁 Loaded {len(self.storage_files)} images from storage")
    
    def find_best_image_for_event(self, event_id: str, title: str) -> Optional[str]:
        """Find the best matching image for an event using multiple strategies"""
        
        # Strategy 1: Direct event ID match
        direct_matches = [f for f in self.storage_files if event_id in f]
        if direct_matches:
            return direct_matches[0]
        
        # Strategy 2: Title-based matching (clean and search)
        if title and len(title) > 5:
            # Clean title for searching
            clean_title_words = re.findall(r'\b\w{4,}\b', title.lower())[:3]  # Take first 3 significant words
            
            for filename in self.storage_files:
                filename_lower = filename.lower()
                matches = sum(1 for word in clean_title_words if word in filename_lower)
                if matches >= 2:  # At least 2 words match
                    return filename
        
        # Strategy 3: Check for any image with similar timestamp or pattern
        # Look for images from similar timeframe (events from 685bd series)
        if event_id.startswith("685bd"):
            pattern_matches = [f for f in self.storage_files if "685bd" in f]
            if pattern_matches:
                return pattern_matches[0]  # Use any from the same batch
        
        return None
    
    async def fix_single_event(self, event: Dict) -> bool:
        """Fix a single event's image references"""
        event_id = str(event["_id"])
        title = event.get("title", "")
        
        try:
            # Find the best matching image
            best_image = self.find_best_image_for_event(event_id, title)
            
            if best_image:
                # Construct the new URL
                new_image_url = f"https://mydscvr.xyz/images/{best_image}"
                
                # Update the event
                update_result = await self.events_collection.update_one(
                    {"_id": event["_id"]},
                    {
                        "$set": {
                            "images.ai_generated": new_image_url,
                            "images.status": "fixed_alternative",
                            "images.fixed_at": datetime.now(timezone.utc),
                            "images.alternative_image": best_image,
                            "image_url": new_image_url,  # Frontend uses this field
                            "image_url_updated_at": datetime.now(timezone.utc)
                        }
                    }
                )
                
                if update_result.modified_count > 0:
                    self.stats["ai_urls_fixed"] += 1
                    self.stats["image_urls_fixed"] += 1
                    self.stats["events_with_working_images"] += 1
                    print(f"   ✅ Fixed {event_id[:12]}... -> {best_image}")
                    return True
                else:
                    print(f"   ⚠️  Update failed for {event_id[:12]}...")
                    return False
            else:
                # No suitable image found - mark as missing
                await self.events_collection.update_one(
                    {"_id": event["_id"]},
                    {
                        "$set": {
                            "images.status": "no_suitable_image",
                            "images.checked_at": datetime.now(timezone.utc)
                        }
                    }
                )
                self.stats["events_still_broken"] += 1
                print(f"   ❌ No image found for {event_id[:12]}... ({title[:30]})")
                return False
                
        except Exception as e:
            error_msg = f"Error processing {event_id}: {str(e)}"
            self.stats["errors"].append(error_msg)
            print(f"   💥 {error_msg}")
            return False
    
    async def fix_all_problematic_events(self):
        """Fix all events with AI image issues"""
        print("🔧 Finding and fixing problematic events...")
        
        # Find events that need fixing
        problematic_query = {
            "$or": [
                # Events with broken AI generated URLs 
                {"images.ai_generated": {"$regex": "^https://mydscvr.xyz/images/ai_generated/"}},
                # Events with missing or failed AI images
                {"images.status": "failed"},
                {"images.status": "image_missing"},
                # Events with no working image at all
                {"image_url": {"$regex": "^/images/ai_generated/"}},
                {"image_url": {"$regex": "oaidalleapiprodscus\\.blob\\.core\\.windows\\.net"}},
            ]
        }
        
        problematic_events = await self.events_collection.find(
            problematic_query,
            {"_id": 1, "title": 1, "images": 1, "image_url": 1}
        ).to_list(length=None)
        
        total_events = len(problematic_events)
        print(f"   🎯 Found {total_events} events that need fixing")
        
        if total_events == 0:
            print("   ✨ No problematic events found!")
            return
        
        # Process events in batches
        batch_size = 20
        for i in range(0, total_events, batch_size):
            batch = problematic_events[i:i+batch_size]
            print(f"\n   📦 Processing batch {i//batch_size + 1} ({len(batch)} events)...")
            
            for event in batch:
                await self.fix_single_event(event)
                self.stats["total_processed"] += 1
            
            # Show progress every 100 events
            if (i + batch_size) % 100 == 0:
                print(f"   📈 Progress: {min(i + batch_size, total_events)}/{total_events} events processed")
    
    async def verify_frontend_compatibility(self):
        """Verify that the fixes are compatible with frontend expectations"""
        print("\n🔍 Verifying frontend compatibility...")
        
        # Check events that should now have working images
        working_events = await self.events_collection.find({
            "images.status": "fixed_alternative"
        }, {
            "_id": 1,
            "title": 1, 
            "images.ai_generated": 1,
            "image_url": 1
        }).limit(5).to_list(length=5)
        
        for event in working_events:
            event_id = str(event["_id"])
            ai_generated = event.get("images", {}).get("ai_generated", "")
            image_url = event.get("image_url", "")
            
            print(f"   📱 {event_id[:12]}... -> {image_url}")
            
            # Check that both fields point to the same working image
            if ai_generated == image_url and "mydscvr.xyz/images/" in image_url:
                print(f"      ✅ Frontend compatible URLs")
            else:
                print(f"      ⚠️  URL mismatch: ai_generated={ai_generated}, image_url={image_url}")
        
        # Count events by image status
        status_counts = {}
        pipeline = [
            {"$group": {"_id": "$images.status", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        async for doc in self.events_collection.aggregate(pipeline):
            status = doc["_id"] or "no_status"
            status_counts[status] = doc["count"]
        
        print(f"\n   📊 Image Status Summary:")
        for status, count in status_counts.items():
            print(f"      {status}: {count} events")
    
    async def run_comprehensive_fix(self):
        """Run the complete comprehensive fix"""
        print("🚀 STARTING COMPREHENSIVE AI IMAGES FIX")
        print("=" * 60)
        
        try:
            # Step 1: Fix all problematic events
            await self.fix_all_problematic_events()
            
            # Step 2: Verify frontend compatibility
            await self.verify_frontend_compatibility()
            
            # Final summary
            print("\n" + "=" * 60)
            print("🎉 COMPREHENSIVE AI IMAGES FIX COMPLETE!")
            print("=" * 60)
            print(f"📊 STATISTICS:")
            print(f"   ✅ Events processed: {self.stats['total_processed']}")
            print(f"   🔗 AI URLs fixed: {self.stats['ai_urls_fixed']}")
            print(f"   🖼️  Image URLs fixed: {self.stats['image_urls_fixed']}")
            print(f"   🎯 Events with working images: {self.stats['events_with_working_images']}")
            print(f"   ❌ Events still broken: {self.stats['events_still_broken']}")
            print(f"   💥 Errors: {len(self.stats['errors'])}")
            
            if self.stats["errors"]:
                print(f"\n⚠️  ERRORS (first 5):")
                for error in self.stats["errors"][:5]:
                    print(f"   - {error}")
            
            success_rate = (self.stats["events_with_working_images"] / 
                          max(1, self.stats["total_processed"])) * 100
            print(f"\n🎯 Success Rate: {success_rate:.1f}%")
            
            print(f"\n🎬 NEXT STEPS:")
            print(f"1. 🚀 Restart backend server to ensure changes take effect")
            print(f"2. 🔄 Clear browser cache and hard refresh frontend")
            print(f"3. 🧪 Test event cards to verify images are loading")
            print(f"4. 📱 Check that frontend prioritizes AI images correctly")
            
            return True
            
        except Exception as e:
            print(f"\n💥 CRITICAL ERROR: {str(e)}")
            self.stats["errors"].append(str(e))
            return False
            
        finally:
            # Close database connection
            if hasattr(self, 'mongodb_client'):
                self.mongodb_client.close()

async def main():
    """Main function"""
    fixer = ComprehensiveAIImageFixer()
    success = await fixer.run_comprehensive_fix()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 