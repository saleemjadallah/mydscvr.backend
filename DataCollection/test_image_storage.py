#!/usr/bin/env python3
"""
Test AI Image Generation with Permanent Storage
Tests the enhanced HybridAIImageService with Backend ImageService integration
"""

import os
import sys
import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'Mongo.env'))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'AI_API.env'))

# Import after path setup
from ai_image_service_hybrid import HybridAIImageService


async def test_permanent_storage():
    """Test AI image generation with permanent storage"""

    print("🧪 Testing AI Image Generation with Permanent Storage")
    print("=" * 60)

    # Connect to MongoDB
    mongodb_uri = os.getenv('Mongo_URI')
    if not mongodb_uri:
        print("❌ MongoDB URI not found in environment variables")
        return

    client = AsyncIOMotorClient(mongodb_uri, tlsInsecure=True)
    db = client['DXB']

    try:
        # Initialize the enhanced hybrid service
        print("🔧 Initializing Enhanced Hybrid AI Image Service...")
        hybrid_service = HybridAIImageService()

        print("✅ Service initialized")
        print(f"📁 ImageService available: {hybrid_service.image_service is not None}")

        # Find a test event without AI image
        print("\n🔍 Finding test event...")
        test_event = await db.events.find_one({
            "$or": [
                {"images.ai_generated": {"$exists": False}},
                {"images.ai_generated": {"$regex": "placeholder"}},
                {"images.ai_generated": None}
            ]
        })

        if not test_event:
            print("⚠️ No test event found without AI image")
            # Create a mock event for testing
            test_event = {
                "_id": "test_event_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
                "title": "Test Event - AI Image Generation",
                "description": ("A beautiful outdoor festival celebrating art and culture in Dubai Marina "
                                "with live music, food vendors, and stunning waterfront views. The event "
                                "features contemporary performances against the backdrop of Dubai's iconic skyline."),
                "venue": {
                    "name": "Dubai Marina Walk",
                    "area": "Dubai Marina"
                },
                "date_time": {
                    "start": datetime.now().isoformat()
                }
            }
            print(f"🎭 Created mock event: {test_event['title']}")
        else:
            print(f"🎯 Found test event: {test_event.get('title', 'Unknown Title')}")

        print(f"📝 Event ID: {test_event['_id']}")
        print(f"📝 Description: {test_event.get('description', 'No description')[:100]}...")

        # Test image generation
        print("\n🎨 Generating AI image with permanent storage...")
        start_time = datetime.now()

        image_url = await hybrid_service.generate_image(test_event)

        generation_time = (datetime.now() - start_time).total_seconds()

        if image_url:
            print(f"✅ Image generated successfully in {generation_time:.1f}s")
            print(f"🔗 Image URL: {image_url}")

            # Check if it's permanent or temporary
            if "api.mydscvr.ai" in image_url:
                print("🎯 ✅ PERMANENT STORAGE: Image stored on backend server")
                storage_type = "permanent"
            elif "oaidalleapiprodscus.blob.core.windows.net" in image_url:
                print("⚠️ TEMPORARY STORAGE: Using OpenAI temporary URL")
                storage_type = "temporary"
            else:
                print("❓ UNKNOWN STORAGE: Unrecognized URL pattern")
                storage_type = "unknown"

            # Test updating the event in database
            print("\n💾 Updating event in database...")
            prompt_used = hybrid_service._create_hybrid_prompt(test_event)
            update_success = await hybrid_service.update_event_with_image(
                db, test_event['_id'], image_url, prompt_used
            )

            if update_success:
                print("✅ Event updated successfully in database")

                # Verify the update
                updated_event = await db.events.find_one({"_id": test_event['_id']})
                if updated_event and updated_event.get('images', {}).get('ai_generated'):
                    print("✅ Verification: Image URL stored in database")
                    storage_type_db = updated_event.get('images', {}).get('storage_type', 'unknown')
                    print(f"📊 Storage type: {storage_type_db}")
                    generation_method = updated_event.get('images', {}).get('generation_method', 'unknown')
                    print(f"🎯 Generation method: {generation_method}")
                else:
                    print("❌ Verification failed: Image not found in database")
            else:
                print("❌ Failed to update event in database")

            # Test results summary
            print("\n" + "=" * 60)
            print("📊 TEST RESULTS SUMMARY")
            print("=" * 60)
            print("🎨 Image Generation: ✅ SUCCESS")
            print(f"⏱️ Generation Time: {generation_time:.1f} seconds")
            print(f"💾 Storage Type: {storage_type.upper()}")
            print(f"🔗 Image URL: {image_url}")
            print(f"📝 Database Update: {'✅ SUCCESS' if update_success else '❌ FAILED'}")

            if storage_type == "permanent":
                print("\n🎉 EXCELLENT! AI image generation with permanent storage is working!")
                print("🚀 Next cronjob will generate permanent images automatically")
            else:
                print("\n⚠️ WARNING! Permanent storage not working, using temporary URLs")
                print("🔧 Check Backend ImageService configuration")

        else:
            print("❌ Failed to generate image")
            print("\n📊 TEST RESULTS SUMMARY")
            print("=" * 60)
            print("🎨 Image Generation: ❌ FAILED")
            print("🔧 Check AI_API.env and OpenAI API key")

    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        client.close()
        print("\n🔚 Test completed")


if __name__ == "__main__":
    asyncio.run(test_permanent_storage())
