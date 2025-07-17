#!/usr/bin/env python3
"""
Update all events to use S3 URLs for images
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import re

load_dotenv('Backend.env')

async def update_events_with_s3_urls():
    """Update all events to use S3 URLs instead of local paths"""
    
    # MongoDB connection
    client = AsyncIOMotorClient(os.getenv('MONGODB_URL'))
    db = client['DXB']
    
    print("🔍 Finding events with local image paths...")
    
    # Find all events with ai_generated images
    cursor = db.events.find({
        'images.ai_generated': {'$exists': True, '$ne': None}
    })
    
    total_updated = 0
    total_processed = 0
    
    async for event in cursor:
        total_processed += 1
        
        if 'images' in event and 'ai_generated' in event['images']:
            local_path = event['images']['ai_generated']
            
            # Extract filename from various path formats
            filename = None
            
            # Pattern 1: /storage/images/filename.jpg
            if '/storage/images/' in local_path:
                filename = local_path.split('/storage/images/')[-1]
            # Pattern 2: Full URL with storage path
            elif 'storage/images/' in local_path:
                filename = local_path.split('storage/images/')[-1]
            # Pattern 3: Just the filename
            elif '/' not in local_path and '.' in local_path:
                filename = local_path
                
            if filename:
                # Construct S3 URL
                s3_url = f"https://mydscvr-event-images.s3.me-central-1.amazonaws.com/ai-images/{filename}"
                
                # Update the event
                update_result = await db.events.update_one(
                    {'_id': event['_id']},
                    {
                        '$set': {
                            'images.s3_url': s3_url,
                            'images.storage_type': 's3',
                            'images.original_local_path': local_path,
                            'images.ai_generated': s3_url  # Update the main field to use S3
                        }
                    }
                )
                
                if update_result.modified_count > 0:
                    total_updated += 1
                    if total_updated % 100 == 0:
                        print(f"  Updated {total_updated} events...")
    
    print(f"\n✅ Update complete!")
    print(f"  Total events processed: {total_processed}")
    print(f"  Events updated with S3 URLs: {total_updated}")
    
    # Verify the update
    s3_count = await db.events.count_documents({'images.s3_url': {'$exists': True}})
    print(f"  Total events with S3 URLs: {s3_count}")
    
    client.close()

if __name__ == "__main__":
    print("🚀 Updating events to use S3 URLs")
    print("==================================")
    asyncio.run(update_events_with_s3_urls())