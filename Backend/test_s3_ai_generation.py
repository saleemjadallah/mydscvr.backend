#!/usr/bin/env python3
"""
Test script for AI image generation with S3 storage
Tests the flow with a single active event
"""

import asyncio
import sys
import os
from datetime import datetime
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv

# Add DataCollection to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'DataCollection', 'mydscvr-datacollection-repo'))

# Import the S3 AI service
from ai_image_service_s3 import AIImageServiceS3

# Load environment
load_dotenv('Backend.env')

async def test_ai_generation():
    """Test AI image generation with S3 storage"""
    
    print("🧪 Testing AI Image Generation with S3 Storage")
    print("=" * 50)
    
    # Connect to MongoDB
    mongo_url = os.getenv('MONGODB_URL')
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client['DXB']
    
    # Find one active event that needs an image
    test_event = db.events.find_one({
        "status": "active",
        "images.needs_regeneration": True
    })
    
    if not test_event:
        print("❌ No active events found needing regeneration")
        return
    
    print(f"\n📋 Test Event:")
    print(f"  Name: {test_event.get('name', 'Unnamed')}")
    print(f"  Category: {test_event.get('category', 'uncategorized')}")
    print(f"  Venue: {test_event.get('venue', {}).get('name', 'Unknown')}")
    
    # Initialize AI service
    print("\n🚀 Initializing AI Image Service...")
    
    # Create a temporary env file for the test
    with open('/Users/saleemjadallah/Desktop/DXB-events/DataCollection/mydscvr-datacollection-repo/AI_API.env', 'w') as f:
        f.write(f"OPENAI_API_KEY={os.getenv('OPENAI_API_KEY')}\n")
        f.write(f"AWS_ACCESS_KEY_ID={os.getenv('AWS_ACCESS_KEY_ID')}\n")
        f.write(f"AWS_SECRET_ACCESS_KEY={os.getenv('AWS_SECRET_ACCESS_KEY')}\n")
        f.write(f"S3_BUCKET_NAME={os.getenv('S3_BUCKET_NAME', 'mydscvr-event-images')}\n")
        f.write(f"S3_REGION={os.getenv('S3_REGION', 'me-central-1')}\n")
    
    try:
        # Convert to async MongoDB client for the service
        from motor.motor_asyncio import AsyncIOMotorClient
        async_client = AsyncIOMotorClient(mongo_url, tlsCAFile=certifi.where())
        async_db = async_client['DXB']
        
        service = AIImageServiceS3()
        
        print("\n🎨 Generating AI image...")
        
        # Generate and store image
        image_url = await service.generate_and_store_image(test_event)
        
        if image_url:
            print(f"\n✅ Successfully generated image!")
            print(f"  URL: {image_url}")
            
            # Update the event
            success = await service.update_event_with_image(
                async_db, 
                test_event['_id'], 
                image_url
            )
            
            if success:
                print(f"\n✅ Successfully updated event in database!")
                
                # Verify the update
                updated_event = await async_db.events.find_one({"_id": test_event['_id']})
                if updated_event:
                    ai_image = updated_event.get('images', {}).get('ai_generated')
                    storage_type = updated_event.get('images', {}).get('storage_type')
                    print(f"\n📊 Verification:")
                    print(f"  AI Image URL: {ai_image}")
                    print(f"  Storage Type: {storage_type}")
                    print(f"  URL contains S3: {'s3.amazonaws.com' in str(ai_image)}")
            else:
                print("❌ Failed to update event in database")
        else:
            print("❌ Failed to generate image")
            
        if 'async_client' in locals():
            await async_client.close()
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up temp env file
        try:
            os.remove('/Users/saleemjadallah/Desktop/DXB-events/DataCollection/mydscvr-datacollection-repo/AI_API.env')
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_ai_generation())