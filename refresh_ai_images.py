#!/usr/bin/env python3
"""
Refresh AI Images Script
Generates fresh AI images for events to replace expired temporary URLs
"""

import asyncio
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from dotenv import load_dotenv

# Import our fixed AI service
from ai_image_service_fixed import FixedHybridAIImageService

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'Mongo.env'))


async def refresh_ai_images_batch():
    """Refresh AI images for a batch of events to provide immediate visible results"""
    
    print("🔄 Refreshing AI Images for Frontend Display")
    print("=" * 50)
    print("This will generate fresh 2-hour valid URLs for immediate viewing")
    print()
    
    # Connect to MongoDB
    mongodb_uri = os.getenv('Mongo_URI')
    if not mongodb_uri:
        print("❌ MongoDB URI not found in environment")
        return
    
    client = AsyncIOMotorClient(mongodb_uri)
    db = client['DXB']
    
    try:
        # Initialize AI service
        ai_service = FixedHybridAIImageService()
        
        # Get events with expired or no AI images (limit to 20 for quick results)
        events = await db.events.find({
            "$or": [
                {"image_url": {"$exists": False}},
                {"image_url": None},
                {"image_url": ""},
                {"images.ai_generated": {"$regex": "st=2025.*se=2025", "$options": "i"}}  # Expired URLs
            ]
        }).limit(20).to_list(length=None)
        
        print(f"📊 Found {len(events)} events needing fresh AI images")
        
        if not events:
            print("✅ No events need image refresh!")
            return
        
        successful_updates = 0
        failed_updates = 0
        
        for i, event in enumerate(events, 1):
            event_title = event.get('title', 'Unknown Event')[:50]
            event_id = str(event.get('_id'))
            
            print(f"\n{i:2d}/20 🎨 Generating for: {event_title}")
            
            try:
                # Generate fresh AI image
                fresh_image_url = await ai_service.generate_image(event)
                
                if fresh_image_url:
                    # Update event with fresh URL
                    prompt = ai_service._create_prompt(event)
                    success = await ai_service.update_event_with_image(
                        db, event_id, fresh_image_url, prompt
                    )
                    
                    if success:
                        print(f"      ✅ Fresh image: {fresh_image_url[:80]}...")
                        successful_updates += 1
                    else:
                        print(f"      ❌ Failed to update database")
                        failed_updates += 1
                else:
                    print(f"      ❌ Failed to generate image")
                    failed_updates += 1
                    
            except Exception as e:
                print(f"      ❌ Error: {str(e)}")
                failed_updates += 1
            
            # Small delay to be respectful to OpenAI API
            if i < len(events):
                await asyncio.sleep(2)
        
        print(f"\n📊 Results Summary:")
        print(f"✅ Successfully refreshed: {successful_updates}")
        print(f"❌ Failed: {failed_updates}")
        print(f"📈 Success rate: {successful_updates/(successful_updates+failed_updates)*100:.1f}%")
        
        if successful_updates > 0:
            print(f"\n🎯 Action Required:")
            print(f"1. Check frontend at mydscvr.ai to see fresh AI images")
            print(f"2. Fresh URLs are valid for 2 hours from generation time")
            print(f"3. Consider setting up automatic image refresh for long-term solution")
        
    except Exception as e:
        print(f"❌ Script failed: {str(e)}")
        logger.error(f"Script error: {str(e)}")
    finally:
        client.close()


async def check_current_image_status():
    """Check current status of AI images in database"""
    
    print("🔍 Checking Current AI Image Status")
    print("=" * 40)
    
    mongodb_uri = os.getenv('Mongo_URI')
    client = AsyncIOMotorClient(mongodb_uri)
    db = client['DXB']
    
    try:
        # Count different image states
        total_events = await db.events.count_documents({})
        
        # Events with image_url
        with_image_url = await db.events.count_documents({
            "image_url": {"$exists": True, "$ne": None, "$ne": ""}
        })
        
        # Events with OpenAI URLs (temporary)
        with_openai_urls = await db.events.count_documents({
            "image_url": {"$regex": "oaidalleapiprodscus", "$options": "i"}
        })
        
        # Events with completed AI generation status
        with_ai_status = await db.events.count_documents({
            "images.status": "completed_hybrid"
        })
        
        print(f"📊 Database Statistics:")
        print(f"   Total events: {total_events:,}")
        print(f"   Events with image_url: {with_image_url:,}")
        print(f"   Events with OpenAI URLs: {with_openai_urls:,}")
        print(f"   Events with AI status: {with_ai_status:,}")
        print(f"   Coverage: {with_image_url/total_events*100:.1f}%")
        
        # Check for expired URLs (rough estimate based on dates in URL)
        potentially_expired = await db.events.count_documents({
            "image_url": {"$regex": "se=2025-07-[0-3]", "$options": "i"}
        })
        
        print(f"   Potentially expired URLs: {potentially_expired:,}")
        
    except Exception as e:
        print(f"❌ Status check failed: {str(e)}")
    finally:
        client.close()


if __name__ == "__main__":
    print("🚀 AI Image Refresh Tool")
    print("========================")
    print()
    
    # First check current status
    asyncio.run(check_current_image_status())
    print()
    
    # Then refresh images
    asyncio.run(refresh_ai_images_batch()) 