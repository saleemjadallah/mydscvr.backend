#!/usr/bin/env python3
"""
Migrate Images to S3 Storage
Transfers all local images to S3 and updates database references
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import mimetypes
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from dotenv import load_dotenv

# Add Backend path for imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from utils.s3_image_service import S3ImageService
from config import settings

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', 'Backend.env'))

class ImageMigrator:
    def __init__(self):
        self.s3_service = None
        self.db = None
        self.client = None
        self.stats = {
            'total_events': 0,
            'events_with_local_images': 0,
            'successfully_migrated': 0,
            'failed_migrations': 0,
            'already_s3': 0,
            'database_updates': 0
        }
        
    async def initialize(self):
        """Initialize S3 service and database connection"""
        print("🔧 Initializing S3 Migration Service...")
        
        # Check for required AWS credentials
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        s3_bucket = os.getenv('S3_BUCKET_NAME', 'mydscvr-event-images')
        aws_region = os.getenv('AWS_REGION', 'me-central-1')
        
        if not aws_access_key or not aws_secret_key:
            print("❌ AWS credentials not found in environment variables")
            print("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
            return False
            
        # Initialize S3 service
        try:
            self.s3_service = S3ImageService(
                bucket_name=s3_bucket,
                region=aws_region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )
            print(f"✅ S3 service initialized: {s3_bucket} in {aws_region}")
        except Exception as e:
            print(f"❌ Failed to initialize S3 service: {e}")
            return False
            
        # Initialize database connection
        mongodb_uri = os.getenv('MONGODB_URL')
        if not mongodb_uri:
            print("❌ MongoDB URI not found in environment")
            return False
            
        try:
            self.client = AsyncIOMotorClient(mongodb_uri)
            self.db = self.client['DXB']
            print("✅ Database connection established")
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            return False
            
        return True
        
    async def find_local_images(self) -> List[Dict]:
        """Find all events with local image references"""
        print("🔍 Scanning for events with local images...")
        
        # Find events with local image paths
        local_image_patterns = [
            {"image_url": {"$regex": "^/images/"}},
            {"image_url": {"$regex": "^https://mydscvr.xyz/images/"}},
            {"images.ai_generated": {"$regex": "^/images/"}},
            {"images.ai_generated": {"$regex": "^https://mydscvr.xyz/images/"}}
        ]
        
        events = await self.db.events.find({
            "$or": local_image_patterns
        }).to_list(length=None)
        
        self.stats['total_events'] = await self.db.events.count_documents({})
        self.stats['events_with_local_images'] = len(events)
        
        print(f"📊 Found {len(events)} events with local images out of {self.stats['total_events']} total events")
        
        return events
        
    async def migrate_event_images(self, event: Dict) -> bool:
        """Migrate images for a single event"""
        event_id = event['_id']
        event_title = event.get('title', 'Unknown Event')
        migrated_any = False
        update_doc = {}
        
        try:
            # Migrate main image_url
            if 'image_url' in event:
                new_url = await self._migrate_single_image(event['image_url'], event_id, 'main')
                if new_url and new_url != event['image_url']:
                    update_doc['image_url'] = new_url
                    migrated_any = True
            
            # Migrate images.ai_generated
            if 'images' in event and 'ai_generated' in event['images']:
                new_url = await self._migrate_single_image(event['images']['ai_generated'], event_id, 'ai_generated')
                if new_url and new_url != event['images']['ai_generated']:
                    update_doc['images.ai_generated'] = new_url
                    migrated_any = True
                    
            # Migrate image_urls array
            if 'image_urls' in event and isinstance(event['image_urls'], list):
                new_urls = []
                for i, img_url in enumerate(event['image_urls']):
                    new_url = await self._migrate_single_image(img_url, event_id, f'array_{i}')
                    new_urls.append(new_url if new_url else img_url)
                    if new_url and new_url != img_url:
                        migrated_any = True
                        
                if migrated_any:
                    update_doc['image_urls'] = new_urls
            
            # Update database if any migrations occurred
            if update_doc:
                await self.db.events.update_one(
                    {"_id": event_id},
                    {"$set": update_doc}
                )
                self.stats['database_updates'] += 1
                print(f"✅ Migrated images for: {event_title[:50]}...")
                
            return migrated_any
            
        except Exception as e:
            print(f"❌ Failed to migrate images for {event_title}: {e}")
            return False
            
    async def _migrate_single_image(self, image_url: str, event_id: str, image_type: str) -> Optional[str]:
        """Migrate a single image URL to S3"""
        if not image_url:
            return None
            
        # Skip if already S3 URL
        if any(pattern in str(image_url) for pattern in ['s3.amazonaws.com', 's3.me-central-1.amazonaws.com', 'cloudfront.net']):
            self.stats['already_s3'] += 1
            return None
            
        # Handle local file paths
        if image_url.startswith('/images/'):
            # Local server path
            local_path = f"/var/www/html{image_url}"  # Adjust path as needed
        elif image_url.startswith('https://mydscvr.xyz/images/'):
            # Extract local path from URL
            local_filename = image_url.split('/images/')[-1]
            local_path = f"/var/www/html/images/{local_filename}"
        else:
            # Skip non-local URLs
            return None
            
        # Check if local file exists
        if not os.path.exists(local_path):
            print(f"⚠️  Local file not found: {local_path}")
            return None
            
        try:
            # Read local file
            with open(local_path, 'rb') as f:
                image_data = f.read()
                
            # Generate S3 filename
            filename = f"{event_id}_{image_type}_{Path(local_path).name}"
            
            # Upload to S3
            s3_url = self.s3_service.upload_image_from_bytes(
                image_data,
                filename,
                content_type=mimetypes.guess_type(local_path)[0] or 'image/jpeg'
            )
            
            if s3_url:
                self.stats['successfully_migrated'] += 1
                return s3_url
            else:
                self.stats['failed_migrations'] += 1
                return None
                
        except Exception as e:
            print(f"❌ Failed to migrate {local_path}: {e}")
            self.stats['failed_migrations'] += 1
            return None
            
    async def cleanup_local_images(self, dry_run: bool = True):
        """Clean up local images after successful migration"""
        print(f"🧹 {'Simulating' if dry_run else 'Performing'} local image cleanup...")
        
        # Find events with S3 images
        s3_events = await self.db.events.find({
            "$or": [
                {"image_url": {"$regex": "s3.amazonaws.com|cloudfront.net"}},
                {"images.ai_generated": {"$regex": "s3.amazonaws.com|cloudfront.net"}}
            ]
        }).to_list(length=None)
        
        cleanup_count = 0
        for event in s3_events:
            # Check if we can safely remove local files
            local_paths = []
            
            # Build list of potential local paths
            if 'image_url' in event:
                original_url = event.get('_original_image_url', event['image_url'])
                if original_url and original_url.startswith('/images/'):
                    local_paths.append(f"/var/www/html{original_url}")
                    
            if dry_run:
                if local_paths:
                    print(f"Would remove: {', '.join(local_paths)}")
                    cleanup_count += len(local_paths)
            else:
                for path in local_paths:
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                            cleanup_count += 1
                            print(f"🗑️  Removed: {path}")
                    except Exception as e:
                        print(f"❌ Failed to remove {path}: {e}")
                        
        print(f"{'Would clean up' if dry_run else 'Cleaned up'} {cleanup_count} local files")
        
    async def run_migration(self, cleanup: bool = False):
        """Run the complete migration process"""
        print("🚀 Starting Image Migration to S3")
        print("=" * 50)
        
        if not await self.initialize():
            return False
            
        # Find events with local images
        events = await self.find_local_images()
        
        if not events:
            print("✅ No local images found to migrate!")
            return True
            
        # Process events in batches
        batch_size = 10
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            print(f"\n📦 Processing batch {i//batch_size + 1} ({len(batch)} events)")
            
            # Process batch
            tasks = [self.migrate_event_images(event) for event in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successful migrations
            successful = sum(1 for r in results if r is True)
            failed = sum(1 for r in results if isinstance(r, Exception) or r is False)
            
            print(f"   ✅ {successful} successful, ❌ {failed} failed")
            
            # Small delay between batches
            if i + batch_size < len(events):
                await asyncio.sleep(1)
                
        # Print final statistics
        print(f"\n📊 Migration Complete!")
        print(f"=" * 50)
        for key, value in self.stats.items():
            print(f"{key.replace('_', ' ').title()}: {value:,}")
            
        # Cleanup if requested
        if cleanup:
            await self.cleanup_local_images(dry_run=False)
            
        return True
        
    async def verify_migration(self):
        """Verify the migration was successful"""
        print("\n🔍 Verifying Migration...")
        print("=" * 30)
        
        # Check for remaining local images
        remaining_local = await self.db.events.count_documents({
            "$or": [
                {"image_url": {"$regex": "^/images/"}},
                {"image_url": {"$regex": "^https://mydscvr.xyz/images/"}},
                {"images.ai_generated": {"$regex": "^/images/"}},
                {"images.ai_generated": {"$regex": "^https://mydscvr.xyz/images/"}}
            ]
        })
        
        # Check S3 images
        s3_images = await self.db.events.count_documents({
            "$or": [
                {"image_url": {"$regex": "s3.amazonaws.com|cloudfront.net"}},
                {"images.ai_generated": {"$regex": "s3.amazonaws.com|cloudfront.net"}}
            ]
        })
        
        print(f"Remaining local images: {remaining_local}")
        print(f"S3 images: {s3_images}")
        
        if remaining_local == 0:
            print("✅ All images successfully migrated to S3!")
        else:
            print(f"⚠️  {remaining_local} images still using local storage")
            
        return remaining_local == 0
        
    async def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()


async def main():
    """Main migration function"""
    migrator = ImageMigrator()
    
    try:
        # Run migration
        success = await migrator.run_migration(cleanup=False)
        
        if success:
            # Verify migration
            await migrator.verify_migration()
            
            # Ask about cleanup
            print("\n" + "=" * 50)
            response = input("Do you want to clean up local images? (y/N): ").lower().strip()
            
            if response == 'y':
                await migrator.cleanup_local_images(dry_run=False)
                
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        logger.error(f"Migration error: {e}")
    finally:
        await migrator.close()


if __name__ == "__main__":
    asyncio.run(main())