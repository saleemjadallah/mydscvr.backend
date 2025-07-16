#!/usr/bin/env python3
"""
Check AI Image Duplication Script
Analyzes current AI image generation patterns and prevents duplicates
"""

import asyncio
import os
import sys
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from dotenv import load_dotenv

# Add Backend path for imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from utils.ai_image_monitor import get_monitor

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', 'Backend.env'))

async def analyze_ai_image_status():
    """Analyze current AI image generation status"""
    
    print("🔍 Analyzing AI Image Generation Status")
    print("="*50)
    
    # Connect to MongoDB
    mongodb_uri = os.getenv('Mongo_URI')
    if not mongodb_uri:
        print("❌ MongoDB URI not found in environment")
        return
    
    client = AsyncIOMotorClient(mongodb_uri)
    db = client['DXB']
    
    try:
        monitor = get_monitor()
        stats = await monitor.get_generation_stats(db)
        
        print(f"📊 Current Statistics:")
        print(f"   Events with AI images: {stats['events_with_ai_images']:,}")
        print(f"   Events without AI images: {stats['events_without_ai_images']:,}")
        print(f"   Recent generation attempts: {stats['recent_generation_attempts']:,}")
        print(f"   API calls last minute: {stats['api_calls_last_minute']:,}")
        print(f"   Cached images: {stats['cached_images']:,}")
        
        # Check for duplicate generation patterns
        print("\n🔍 Checking for Duplicate Generation Patterns...")
        
        # Find events with multiple AI image attempts
        events_with_multiple_images = await db.events.find({
            "$and": [
                {"images.ai_generated": {"$exists": True, "$ne": None, "$ne": ""}},
                {"image_url": {"$regex": "oaidalleapiprodscus|mydscvr-event-images", "$options": "i"}}
            ]
        }).to_list(length=100)
        
        print(f"   Events with multiple AI images: {len(events_with_multiple_images)}")
        
        # Check for recent duplicates
        recent_duplicates = 0
        for event in events_with_multiple_images:
            ai_image = event.get('images', {}).get('ai_generated')
            image_url = event.get('image_url')
            
            if ai_image and image_url and ai_image != image_url:
                recent_duplicates += 1
                if recent_duplicates <= 5:  # Show first 5 examples
                    print(f"      Example: {event.get('title', 'Unknown')[:30]}...")
                    print(f"         AI image: {ai_image[:60]}...")
                    print(f"         Image URL: {image_url[:60]}...")
        
        print(f"   Total events with duplicate images: {recent_duplicates}")
        
        # Check API usage patterns
        print("\n📈 API Usage Analysis:")
        
        # Count events by image source
        openai_images = await db.events.count_documents({
            "image_url": {"$regex": "oaidalleapiprodscus", "$options": "i"}
        })
        
        s3_images = await db.events.count_documents({
            "image_url": {"$regex": "mydscvr-event-images.s3", "$options": "i"}
        })
        
        local_images = await db.events.count_documents({
            "image_url": {"$regex": "/images/events/", "$options": "i"}
        })
        
        print(f"   OpenAI temporary URLs: {openai_images:,}")
        print(f"   S3 stored images: {s3_images:,}")
        print(f"   Local stored images: {local_images:,}")
        
        # Calculate potential savings
        total_ai_images = openai_images + s3_images + local_images
        potential_duplicates = recent_duplicates + (openai_images * 0.3)  # Estimate 30% duplicates
        
        print(f"\n💰 Potential Cost Savings:")
        print(f"   Total AI images generated: {total_ai_images:,}")
        print(f"   Estimated duplicates: {potential_duplicates:.0f}")
        print(f"   Potential cost savings: ${potential_duplicates * 0.04:.2f}")
        
        # Provide recommendations
        print(f"\n🎯 Recommendations:")
        if recent_duplicates > 0:
            print("   ⚠️  Multiple AI images detected for same events")
            print("   ✅ Use the AI image monitor to prevent duplicates")
            print("   ✅ Clean up duplicate images in database")
        
        if openai_images > s3_images:
            print("   ⚠️  Many temporary OpenAI URLs detected")
            print("   ✅ Migrate temporary URLs to permanent S3 storage")
        
        if stats['events_without_ai_images'] > 0:
            print(f"   ℹ️  {stats['events_without_ai_images']} events need AI images")
            print("   ✅ Generate images for events without them")
        
        # Check monitor status
        if monitor:
            print(f"\n✅ AI Image Monitor: Active")
            print(f"   Rate limiting: {monitor.max_api_calls_per_minute} calls/minute")
            print(f"   Retry interval: {monitor.min_retry_interval.total_seconds()/3600:.1f} hours")
        else:
            print(f"\n❌ AI Image Monitor: Not active")
        
    except Exception as e:
        print(f"❌ Analysis failed: {str(e)}")
        logger.error(f"Analysis error: {str(e)}")
    finally:
        client.close()


async def cleanup_duplicate_images():
    """Clean up duplicate AI images in the database"""
    
    print("\n🧹 Cleaning Up Duplicate AI Images")
    print("="*50)
    
    # Connect to MongoDB
    mongodb_uri = os.getenv('Mongo_URI')
    if not mongodb_uri:
        print("❌ MongoDB URI not found in environment")
        return
    
    client = AsyncIOMotorClient(mongodb_uri)
    db = client['DXB']
    
    try:
        # Find events with both ai_generated and image_url
        events_with_duplicates = await db.events.find({
            "$and": [
                {"images.ai_generated": {"$exists": True, "$ne": None, "$ne": ""}},
                {"image_url": {"$exists": True, "$ne": None, "$ne": ""}},
                {"images.ai_generated": {"$ne": "$image_url"}}
            ]
        }).to_list(length=1000)
        
        print(f"Found {len(events_with_duplicates)} events with potential duplicate images")
        
        cleaned_count = 0
        for event in events_with_duplicates:
            event_id = event['_id']
            ai_image = event.get('images', {}).get('ai_generated')
            image_url = event.get('image_url')
            
            # Prefer S3 images over OpenAI temporary URLs
            if 'mydscvr-event-images.s3' in str(ai_image):
                # Keep S3 image, remove image_url if it's temporary
                if 'oaidalleapiprodscus' in str(image_url):
                    await db.events.update_one(
                        {"_id": event_id},
                        {"$set": {"image_url": ai_image}}
                    )
                    cleaned_count += 1
                    
            elif 'mydscvr-event-images.s3' in str(image_url):
                # Keep S3 image in image_url, remove ai_generated if it's temporary
                if 'oaidalleapiprodscus' in str(ai_image):
                    await db.events.update_one(
                        {"_id": event_id},
                        {"$unset": {"images.ai_generated": ""}}
                    )
                    cleaned_count += 1
        
        print(f"✅ Cleaned up {cleaned_count} duplicate image references")
        
    except Exception as e:
        print(f"❌ Cleanup failed: {str(e)}")
        logger.error(f"Cleanup error: {str(e)}")
    finally:
        client.close()


async def main():
    """Main function"""
    print("🚀 AI Image Duplication Checker")
    print("="*50)
    
    # Run analysis
    await analyze_ai_image_status()
    
    # Ask for cleanup
    print("\n" + "="*50)
    response = input("Do you want to clean up duplicate images? (y/N): ").lower().strip()
    
    if response == 'y':
        await cleanup_duplicate_images()
    else:
        print("Skipping cleanup")
    
    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    asyncio.run(main())