#!/usr/bin/env python3
"""
Direct S3 Migration Script
Migrates local images to S3 without dependencies on missing modules
"""

import os
import sys
import asyncio
import boto3
from pathlib import Path
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from botocore.exceptions import NoCredentialsError
import mimetypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv('Backend.env')

class DirectS3Migrator:
    def __init__(self):
        # AWS Configuration
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'mydscvr-event-images')
        self.region = os.getenv('AWS_REGION', 'me-central-1')
        
        # MongoDB Configuration
        self.mongodb_url = os.getenv('MONGODB_URL')
        self.client = None
        self.db = None
        
        # S3 Client
        self.s3_client = None
        
        # Statistics
        self.stats = {
            'total_files': 0,
            'uploaded': 0,
            'skipped': 0,
            'failed': 0,
            'events_updated': 0
        }
        
    async def initialize(self):
        """Initialize S3 and MongoDB connections"""
        print("🔧 Initializing Direct S3 Migration...")
        
        # Initialize S3
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.region
            )
            # Test S3 connection
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            print(f"✅ Connected to S3 bucket: {self.bucket_name}")
        except NoCredentialsError:
            print("❌ AWS credentials not found!")
            return False
        except Exception as e:
            print(f"❌ S3 connection error: {e}")
            return False
            
        # Initialize MongoDB
        try:
            self.client = AsyncIOMotorClient(self.mongodb_url)
            self.db = self.client['DXB']
            await self.client.admin.command('ping')
            print("✅ Connected to MongoDB")
        except Exception as e:
            print(f"❌ MongoDB connection error: {e}")
            return False
            
        return True
        
    async def migrate_images(self):
        """Migrate all images from local storage to S3"""
        local_path = Path('/home/ubuntu/backend/storage/images')
        
        if not local_path.exists():
            print(f"❌ Local storage path not found: {local_path}")
            return
            
        # Get all image files
        image_files = []
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.gif']:
            image_files.extend(local_path.rglob(ext))
            
        self.stats['total_files'] = len(image_files)
        print(f"📸 Found {self.stats['total_files']} images to migrate")
        
        # Process in batches
        batch_size = 10
        for i in range(0, len(image_files), batch_size):
            batch = image_files[i:i+batch_size]
            await self._process_batch(batch, i, len(image_files))
            
    async def _process_batch(self, batch, start_idx, total):
        """Process a batch of images"""
        tasks = []
        for idx, file_path in enumerate(batch):
            print(f"📤 Uploading {start_idx + idx + 1}/{total}: {file_path.name}")
            tasks.append(self._upload_file(file_path))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                print(f"  ❌ Error: {result}")
                self.stats['failed'] += 1
            elif result:
                self.stats['uploaded'] += 1
            else:
                self.stats['skipped'] += 1
                
    async def _upload_file(self, file_path):
        """Upload a single file to S3"""
        try:
            # Determine S3 key from file path
            # Extract relative path from storage/images/
            relative_path = file_path.relative_to('/home/ubuntu/backend/storage/images')
            s3_key = f"ai-images/{relative_path}"
            
            # Get content type
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = 'image/jpeg'
                
            # Upload to S3
            with open(file_path, 'rb') as f:
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=f,
                    ContentType=content_type,
                    CacheControl='public, max-age=31536000'
                )
                
            print(f"  ✅ Uploaded: {s3_key}")
            
            # Update database if this is an event image
            await self._update_database(file_path, s3_key)
            
            return True
            
        except Exception as e:
            print(f"  ❌ Failed to upload {file_path.name}: {e}")
            return False
            
    async def _update_database(self, local_path, s3_key):
        """Update database with new S3 URLs"""
        try:
            # Get filename without extension for matching
            filename = local_path.stem
            
            # Construct S3 URL
            s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            # Find and update events with this image
            local_url_pattern = f"/storage/images/{local_path.name}"
            
            result = await self.db.events.update_many(
                {
                    "$or": [
                        {"images.ai_generated": {"$regex": local_path.name}},
                        {"images.s3_url": {"$exists": False}}
                    ]
                },
                {
                    "$set": {
                        "images.s3_url": s3_url,
                        "images.storage_type": "s3",
                        "images.migrated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                self.stats['events_updated'] += result.modified_count
                print(f"  📝 Updated {result.modified_count} events with S3 URL")
                
        except Exception as e:
            print(f"  ⚠️  Database update error: {e}")
            
    async def show_summary(self):
        """Show migration summary"""
        print("\n" + "="*60)
        print("📊 MIGRATION SUMMARY")
        print("="*60)
        print(f"Total files found: {self.stats['total_files']}")
        print(f"Successfully uploaded: {self.stats['uploaded']}")
        print(f"Skipped: {self.stats['skipped']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"Database records updated: {self.stats['events_updated']}")
        print("="*60)
        
        if self.stats['uploaded'] > 0:
            # Calculate space saved
            saved_gb = 9.9 * (self.stats['uploaded'] / self.stats['total_files'])
            print(f"\n💾 Estimated space saved: {saved_gb:.1f}GB")
            
    async def cleanup(self):
        """Close connections"""
        if self.client:
            self.client.close()
            
async def main():
    migrator = DirectS3Migrator()
    
    if not await migrator.initialize():
        print("❌ Failed to initialize migrator")
        return
        
    try:
        await migrator.migrate_images()
        await migrator.show_summary()
    except KeyboardInterrupt:
        print("\n⚠️  Migration interrupted by user")
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await migrator.cleanup()
        
if __name__ == "__main__":
    print("🚀 Starting Direct S3 Migration")
    print("================================")
    asyncio.run(main())