#!/usr/bin/env python3
"""
Update all events to replace images.ai_generated with S3 URLs
This ensures frontend continues to work without any changes
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('Backend.env')

async def update_ai_generated_to_s3():
    """Replace all images.ai_generated local paths with S3 URLs"""
    
    # MongoDB connection
    client = AsyncIOMotorClient(os.getenv('MONGODB_URL'))
    db = client['DXB']
    
    print("🔄 Updating images.ai_generated to use S3 URLs...")
    
    # Count events before update
    total_events = await db.events.count_documents({'images.s3_url': {'$exists': True}})
    print(f"📊 Found {total_events} events with S3 URLs to update")
    
    # Update all events that have s3_url to use it in ai_generated
    result = await db.events.update_many(
        {
            'images.s3_url': {'$exists': True}
        },
        [
            {
                '$set': {
                    'images.ai_generated': '$images.s3_url',
                    'images.original_local_path': {
                        '$cond': {
                            'if': {'$not': ['$images.original_local_path']},
                            'then': '$images.ai_generated',
                            'else': '$images.original_local_path'
                        }
                    }
                }
            }
        ]
    )
    
    print(f"\n✅ Update complete!")
    print(f"   Modified {result.modified_count} events")
    
    # Verify the update with a sample
    sample = await db.events.find_one({'images.ai_generated': {'$regex': 'amazonaws.com'}})
    if sample:
        print(f"\n📸 Sample updated event:")
        print(f"   Name: {sample.get('name', 'Unknown')}")
        print(f"   AI Generated URL: {sample['images']['ai_generated'][:100]}...")
        
    # Count how many events now have S3 URLs in ai_generated
    s3_in_ai_generated = await db.events.count_documents({
        'images.ai_generated': {'$regex': 'amazonaws.com'}
    })
    print(f"\n📊 Final status:")
    print(f"   Events with S3 URLs in ai_generated field: {s3_in_ai_generated}")
    print(f"   Events with local paths: {total_events - s3_in_ai_generated}")
    
    client.close()
    
    if s3_in_ai_generated == total_events:
        print("\n🎉 SUCCESS! All events are now using S3 URLs")
        print("   The frontend will automatically use S3 images")
        print("   You can now safely delete local storage")
    else:
        print("\n⚠️  Some events may still have local paths")

if __name__ == "__main__":
    print("🚀 Updating AI Generated Images to S3 URLs")
    print("==========================================")
    asyncio.run(update_ai_generated_to_s3())