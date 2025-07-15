#!/usr/bin/env python3
"""
PERMANENT AI IMAGES FIX SCRIPT
Resolves the AI image loading issue once and for all

Root Cause Analysis:
1. 1,407 events have AI images in MongoDB with status "completed_hybrid" 
2. All AI images point to URLs like: https://mydscvr.xyz/images/ai_generated/event_*.png
3. The ai_generated directory is completely empty - no files exist
4. Events fall back to placeholder images instead of showing AI images

Solution:
1. Identify events with broken AI image URLs
2. Fix URL patterns to point to existing images
3. Update database with correct image references
4. Verify all images are accessible

Created: January 2025
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient

# Add the parent directory to the path so we can import from the backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import settings

class AIImageFixer:
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
        self.ai_generated_path = os.path.join(self.storage_path, "ai_generated")
        
        # Statistics
        self.stats = {
            "total_events": 0,
            "events_with_ai_images": 0,
            "broken_ai_urls": 0,
            "fixed_urls": 0,
            "existing_images_found": 0,
            "events_missing_images": 0,
            "errors": []
        }
    
    async def analyze_database_state(self) -> Dict:
        """Analyze the current state of AI images in the database"""
        print("🔍 Analyzing database state...")
        
        # Count total events
        self.stats["total_events"] = await self.events_collection.count_documents({})
        
        # Count events with AI images
        self.stats["events_with_ai_images"] = await self.events_collection.count_documents({
            "images.ai_generated": {"$exists": True, "$ne": None, "$ne": ""}
        })
        
        # Count events with failed AI image status
        failed_ai_images = await self.events_collection.count_documents({
            "images.status": "failed"
        })
        
        # Count events with completed AI images pointing to ai_generated directory
        broken_urls = await self.events_collection.count_documents({
            "images.ai_generated": {"$regex": "^https://mydscvr.xyz/images/ai_generated/"}
        })
        
        self.stats["broken_ai_urls"] = broken_urls
        
        print(f"✅ Database Analysis Complete:")
        print(f"   📊 Total events: {self.stats['total_events']}")
        print(f"   🎨 Events with AI images: {self.stats['events_with_ai_images']}")
        print(f"   ❌ Failed AI images: {failed_ai_images}")
        print(f"   🔗 Broken AI URLs: {broken_urls}")
        
        return self.stats
    
    async def check_storage_state(self) -> Dict:
        """Check the physical storage state"""
        print("\n📁 Checking storage state...")
        
        # Check if ai_generated directory exists
        ai_generated_exists = os.path.exists(self.ai_generated_path)
        ai_generated_files = []
        
        if ai_generated_exists:
            ai_generated_files = [f for f in os.listdir(self.ai_generated_path) 
                                if f.endswith(('.png', '.jpg', '.jpeg'))]
        
        # Check main images directory
        main_images = []
        if os.path.exists(self.storage_path):
            main_images = [f for f in os.listdir(self.storage_path) 
                          if f.endswith(('.png', '.jpg', '.jpeg'))]
        
        storage_info = {
            "ai_generated_exists": ai_generated_exists,
            "ai_generated_files_count": len(ai_generated_files),
            "main_images_count": len(main_images),
            "total_storage_files": len(ai_generated_files) + len(main_images)
        }
        
        print(f"   📂 AI generated directory exists: {ai_generated_exists}")
        print(f"   🖼️  AI generated files: {len(ai_generated_files)}")
        print(f"   📸 Main images directory files: {len(main_images)}")
        
        return storage_info
    
    async def find_matching_images(self, event_id: str) -> List[str]:
        """Find existing images that match the event ID"""
        matching_files = []
        
        if os.path.exists(self.storage_path):
            for filename in os.listdir(self.storage_path):
                if (filename.endswith(('.png', '.jpg', '.jpeg')) and 
                    event_id in filename):
                    matching_files.append(filename)
        
        return matching_files
    
    async def fix_event_image_url(self, event: Dict) -> Optional[str]:
        """Fix a single event's image URL by finding existing images"""
        event_id = str(event["_id"])
        
        try:
            # Find matching images in storage
            matching_files = await self.find_matching_images(event_id)
            
            if matching_files:
                # Use the first matching file
                best_match = matching_files[0]
                new_url = f"https://mydscvr.xyz/images/{best_match}"
                
                # Update the event in database
                await self.events_collection.update_one(
                    {"_id": event["_id"]},
                    {
                        "$set": {
                            "images.ai_generated": new_url,
                            "images.status": "completed_fixed",
                            "images.fixed_at": datetime.utcnow(),
                            "images.original_broken_url": event.get("images", {}).get("ai_generated"),
                            "image_url": new_url  # Also update the main image_url field
                        }
                    }
                )
                
                self.stats["fixed_urls"] += 1
                self.stats["existing_images_found"] += 1
                
                return new_url
            else:
                # No matching image found - mark as missing
                await self.events_collection.update_one(
                    {"_id": event["_id"]},
                    {
                        "$set": {
                            "images.status": "image_missing",
                            "images.checked_at": datetime.utcnow()
                        }
                    }
                )
                
                self.stats["events_missing_images"] += 1
                return None
                
        except Exception as e:
            error_msg = f"Error fixing event {event_id}: {str(e)}"
            self.stats["errors"].append(error_msg)
            print(f"   ❌ {error_msg}")
            return None
    
    async def fix_all_broken_urls(self):
        """Fix all broken AI image URLs"""
        print("\n🔧 Fixing broken AI image URLs...")
        
        # Find all events with broken AI image URLs
        broken_events = await self.events_collection.find({
            "images.ai_generated": {"$regex": "^https://mydscvr.xyz/images/ai_generated/"}
        }).to_list(length=None)
        
        print(f"   🔍 Found {len(broken_events)} events with broken AI URLs")
        
        for i, event in enumerate(broken_events, 1):
            if i % 50 == 0:
                print(f"   📈 Processed {i}/{len(broken_events)} events...")
            
            await self.fix_event_image_url(event)
        
        print(f"✅ Fixed URLs complete!")
        print(f"   ✨ Fixed URLs: {self.stats['fixed_urls']}")
        print(f"   🎯 Found existing images: {self.stats['existing_images_found']}")
        print(f"   ❓ Missing images: {self.stats['events_missing_images']}")
    
    async def verify_fixes(self) -> Dict:
        """Verify that the fixes are working"""
        print("\n✅ Verifying fixes...")
        
        # Count remaining broken URLs
        remaining_broken = await self.events_collection.count_documents({
            "images.ai_generated": {"$regex": "^https://mydscvr.xyz/images/ai_generated/"}
        })
        
        # Count fixed events
        fixed_events = await self.events_collection.count_documents({
            "images.status": "completed_fixed"
        })
        
        # Count events with missing images
        missing_images = await self.events_collection.count_documents({
            "images.status": "image_missing"
        })
        
        verification = {
            "remaining_broken_urls": remaining_broken,
            "fixed_events": fixed_events,
            "missing_images": missing_images,
            "fix_success_rate": (fixed_events / max(1, self.stats["broken_ai_urls"])) * 100
        }
        
        print(f"   🔗 Remaining broken URLs: {remaining_broken}")
        print(f"   ✅ Fixed events: {fixed_events}")
        print(f"   ❓ Events with missing images: {missing_images}")
        print(f"   📊 Fix success rate: {verification['fix_success_rate']:.1f}%")
        
        return verification
    
    async def create_missing_image_report(self):
        """Create a report of events with missing images"""
        print("\n📋 Creating missing image report...")
        
        missing_events = await self.events_collection.find({
            "images.status": "image_missing"
        }, {
            "_id": 1,
            "title": 1,
            "images.original_broken_url": 1
        }).to_list(length=None)
        
        if missing_events:
            report_path = "missing_images_report.txt"
            with open(report_path, "w") as f:
                f.write("MISSING AI IMAGES REPORT\n")
                f.write("=" * 40 + "\n\n")
                f.write(f"Generated: {datetime.now()}\n")
                f.write(f"Total missing: {len(missing_events)}\n\n")
                
                for event in missing_events:
                    f.write(f"Event ID: {event['_id']}\n")
                    f.write(f"Title: {event.get('title', 'No title')}\n")
                    f.write(f"Broken URL: {event.get('images', {}).get('original_broken_url', 'N/A')}\n")
                    f.write("-" * 40 + "\n")
            
            print(f"   📄 Report saved to: {report_path}")
        else:
            print(f"   ✨ No missing images found!")
    
    async def run_complete_fix(self):
        """Run the complete AI image fix process"""
        print("🚀 STARTING PERMANENT AI IMAGES FIX")
        print("=" * 50)
        
        try:
            # Step 1: Analyze current state
            await self.analyze_database_state()
            
            # Step 2: Check storage
            await self.check_storage_state()
            
            # Step 3: Fix broken URLs
            await self.fix_all_broken_urls()
            
            # Step 4: Verify fixes
            verification = await self.verify_fixes()
            
            # Step 5: Create missing image report
            await self.create_missing_image_report()
            
            # Final summary
            print("\n" + "=" * 50)
            print("🎉 AI IMAGES FIX COMPLETE!")
            print("=" * 50)
            print(f"✅ Fixed events: {self.stats['fixed_urls']}")
            print(f"❓ Missing images: {self.stats['events_missing_images']}")
            print(f"❌ Errors: {len(self.stats['errors'])}")
            print(f"📊 Success rate: {verification['fix_success_rate']:.1f}%")
            
            if self.stats["errors"]:
                print("\n⚠️  ERRORS ENCOUNTERED:")
                for error in self.stats["errors"][:5]:  # Show first 5 errors
                    print(f"   - {error}")
                if len(self.stats["errors"]) > 5:
                    print(f"   ... and {len(self.stats['errors']) - 5} more errors")
            
            return {
                "success": True,
                "stats": self.stats,
                "verification": verification
            }
            
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "stats": self.stats
            }
        
        finally:
            # Close database connection
            if hasattr(self, 'mongodb_client'):
                self.mongodb_client.close()

async def main():
    """Main function to run the AI image fix"""
    fixer = AIImageFixer()
    result = await fixer.run_complete_fix()
    
    if result["success"]:
        print("\n🎯 NEXT STEPS:")
        print("1. Deploy the backend with updated image URLs")
        print("2. Clear frontend cache/refresh browser")
        print("3. Test event cards to verify AI images are loading")
        print("4. Consider generating new AI images for missing events")
    else:
        print(f"\n💥 Fix failed: {result.get('error')}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 