#!/usr/bin/env python3
"""
Test the integrated collection with AI image generation
"""

import os
import asyncio
from dotenv import load_dotenv
from enhanced_collection import collect_and_store_events
from loguru import logger

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'DataCollection.env'))

async def test_integrated_collection():
    """Test the full integrated collection pipeline"""
    
    print("🧪 Testing Integrated Collection Pipeline")
    print("=" * 60)
    print("📋 Configuration:")
    print(f"   🔥 Firecrawl: {os.getenv('ENABLE_FIRECRAWL_SUPPLEMENT', 'false')}")
    print(f"   🎨 AI Images: {os.getenv('ENABLE_AI_IMAGE_GENERATION', 'false')}")
    print(f"   📦 Batch Size: {os.getenv('AI_IMAGE_BATCH_SIZE', '5')}")
    print(f"   ⏱️ Batch Delay: {os.getenv('AI_IMAGE_BATCH_DELAY', '10')}s")
    print()
    
    # Set smaller limits for testing
    original_perplexity_limit = os.environ.get('PERPLEXITY_QUERIES_LIMIT')
    original_firecrawl_limit = os.environ.get('FIRECRAWL_PLATINUMLIST_LIMIT')
    
    # Set test limits
    os.environ['PERPLEXITY_QUERIES_LIMIT'] = '3'  # Small test
    os.environ['FIRECRAWL_PLATINUMLIST_LIMIT'] = '2'
    os.environ['FIRECRAWL_TIMEOUT_LIMIT'] = '1'
    os.environ['FIRECRAWL_WHATSON_LIMIT'] = '1'
    
    print("🔬 Test Configuration:")
    print("   📡 Perplexity queries: 3 (test mode)")
    print("   🔥 Firecrawl events: 4 total (test mode)")
    print("   🎨 AI images: Will generate for all stored events")
    print()
    
    try:
        # Run the integrated collection
        print("🚀 Starting integrated collection test...")
        result = await collect_and_store_events()
        
        if result > 0:
            print(f"✅ Test completed successfully!")
            print(f"📊 Total events processed: {result}")
            print("🎨 AI images should be generating in the background...")
        else:
            print("❌ Test failed - no events collected")
    
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Restore original limits
        if original_perplexity_limit:
            os.environ['PERPLEXITY_QUERIES_LIMIT'] = original_perplexity_limit
        if original_firecrawl_limit:
            os.environ['FIRECRAWL_PLATINUMLIST_LIMIT'] = original_firecrawl_limit

async def check_ai_image_progress():
    """Check the progress of AI image generation"""
    
    print("\n🔍 Checking AI Image Generation Progress...")
    
    from motor.motor_asyncio import AsyncIOMotorClient
    
    # Connect to MongoDB
    mongodb_uri = os.getenv('Mongo_URI')
    client = AsyncIOMotorClient(mongodb_uri, tlsInsecure=True)
    db = client['DXB']
    
    try:
        # Count events by image status
        total_events = await db.events.count_documents({})
        
        with_images = await db.events.count_documents({
            "images.ai_generated": {"$exists": True, "$ne": None}
        })
        
        generating = await db.events.count_documents({
            "images.status": "generating"
        })
        
        completed = await db.events.count_documents({
            "images.status": {"$in": ["completed", "completed_hybrid"]}
        })
        
        failed = await db.events.count_documents({
            "images.status": "failed"
        })
        
        print(f"📊 AI Image Generation Status:")
        print(f"   📋 Total events: {total_events}")
        print(f"   🖼️ With AI images: {with_images}")
        print(f"   ✅ Completed: {completed}")
        print(f"   🔄 Generating: {generating}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📈 Completion rate: {(with_images/total_events*100):.1f}%")
        
        # Get recent AI images
        recent_images = await db.events.find({
            "images.ai_generated": {"$exists": True, "$ne": None}
        }).sort("images.generated_at", -1).limit(3).to_list(length=3)
        
        if recent_images:
            print(f"\n🎨 Recent AI Generated Images:")
            for i, event in enumerate(recent_images, 1):
                title = event.get('title', 'Unknown')
                image_url = event.get('images', {}).get('ai_generated', '')
                print(f"   {i}. {title}")
                print(f"      {image_url[:50]}...")
        
    except Exception as e:
        print(f"❌ Error checking progress: {str(e)}")
    
    finally:
        client.close()

if __name__ == "__main__":
    print("🤖 Dubai Events - Integrated Collection Test")
    print("=" * 60)
    
    # Run test
    asyncio.run(test_integrated_collection())
    
    # Wait a bit for AI generation to start
    print("\n⏳ Waiting 30 seconds for AI generation to begin...")
    import time
    time.sleep(30)
    
    # Check progress
    asyncio.run(check_ai_image_progress())