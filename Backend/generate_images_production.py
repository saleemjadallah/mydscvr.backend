#!/usr/bin/env python3
"""
Generate AI images for active events - Production version
Uses environment variables for all secrets (no hardcoded values)
"""

import asyncio
import sys
import os
from datetime import datetime
from pymongo import MongoClient
import certifi
from motor.motor_asyncio import AsyncIOMotorClient
import signal

# Add DataCollection to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'DataCollection', 'mydscvr-datacollection-repo'))

# Import the S3 AI service
from ai_image_service_s3 import AIImageServiceS3

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    print("\n\n⚠️  Shutdown requested. Finishing current batch...")
    shutdown_requested = True

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)

async def generate_images(batch_count=50):
    """Generate AI images for active events using environment variables"""
    
    print("🚀 AI Image Generation for Active Events (Production)")
    print("=" * 60)
    print("Press Ctrl+C to stop gracefully after current batch\n")
    
    # Get MongoDB URL from environment
    mongo_url = os.environ.get('MONGODB_URL')
    if not mongo_url:
        print("❌ Error: MONGODB_URL environment variable not set")
        print("Please ensure all secrets are properly configured in the deployment environment")
        return
    
    # Verify other required environment variables
    required_vars = ['OPENAI_API_KEY', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'S3_BUCKET_NAME', 'S3_REGION']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"❌ Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please ensure all secrets are properly configured in the deployment environment")
        return
    
    try:
        # Setup MongoDB connections
        sync_client = MongoClient(mongo_url, tlsCAFile=certifi.where())
        sync_db = sync_client['DXB']
        
        # Test connection
        sync_db.events.count_documents({})
        print("✅ Successfully connected to MongoDB")
        
    except Exception as e:
        print(f"❌ MongoDB connection error: {str(e)}")
        print("Please verify the MONGODB_URL is correct and accessible")
        return
    
    # Get initial stats
    initial_s3_count = sync_db.events.count_documents({
        'images.generation_method': 'dalle3_with_s3'
    })
    
    # Find events that need images
    events_to_process = list(sync_db.events.find({
        "status": "active",
        "images.needs_regeneration": True
    }).limit(batch_count))
    
    if not events_to_process:
        print("❌ No active events found needing regeneration")
        sync_client.close()
        return
    
    print(f"📋 Found {len(events_to_process)} active events for processing")
    print(f"📊 Current S3 images: {initial_s3_count}")
    print("-" * 60)
    
    # Create temporary AI_API.env file for the service
    env_path = os.path.join(os.path.dirname(__file__), '..', 'DataCollection', 'mydscvr-datacollection-repo', 'AI_API.env')
    
    with open(env_path, 'w') as f:
        f.write(f"OPENAI_API_KEY={os.environ.get('OPENAI_API_KEY')}\n")
        f.write(f"AWS_ACCESS_KEY_ID={os.environ.get('AWS_ACCESS_KEY_ID')}\n")
        f.write(f"AWS_SECRET_ACCESS_KEY={os.environ.get('AWS_SECRET_ACCESS_KEY')}\n")
        f.write(f"S3_BUCKET_NAME={os.environ.get('S3_BUCKET_NAME', 'mydscvr-event-images')}\n")
        f.write(f"S3_REGION={os.environ.get('S3_REGION', 'me-central-1')}\n")
    
    try:
        # Async client for the service
        async_client = AsyncIOMotorClient(mongo_url, tlsCAFile=certifi.where())
        async_db = async_client['DXB']
        
        # Initialize AI service
        service = AIImageServiceS3()
        
        print("\n🎨 Starting AI image generation...")
        start_time = datetime.now()
        
        # Process in smaller batches for better monitoring
        batch_size = 2
        total_processed = 0
        total_successful = 0
        total_failed = 0
        
        for i in range(0, len(events_to_process), batch_size):
            if shutdown_requested:
                print("\n⚠️  Stopping after current batch...")
                break
                
            batch = events_to_process[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(events_to_process) + batch_size - 1) // batch_size
            
            print(f"\n📦 Batch {batch_num}/{total_batches} (Events {i+1}-{min(i+batch_size, len(events_to_process))})")
            
            # Process batch
            batch_start = datetime.now()
            results = await service.process_events_batch(async_db, batch, batch_size=batch_size)
            batch_time = (datetime.now() - batch_start).total_seconds()
            
            # Update counters
            total_processed += len(batch)
            total_successful += results['successful']
            total_failed += results['failed']
            
            # Show batch results
            print(f"   ✅ Successful: {results['successful']}")
            print(f"   ❌ Failed: {results['failed']}")
            print(f"   ⏱️  Batch time: {batch_time:.1f}s")
            
            # Estimate time remaining
            if total_processed < len(events_to_process) and not shutdown_requested:
                avg_time_per_event = (datetime.now() - start_time).total_seconds() / total_processed
                remaining_events = len(events_to_process) - total_processed
                eta_seconds = avg_time_per_event * remaining_events
                eta_minutes = int(eta_seconds / 60)
                eta_seconds = int(eta_seconds % 60)
                print(f"   ⏰ ETA: {eta_minutes}m {eta_seconds}s")
        
        # Final summary
        total_time = (datetime.now() - start_time).total_seconds()
        print("\n" + "=" * 60)
        print("📊 FINAL RESULTS:")
        print(f"   Total processed: {total_processed}/{len(events_to_process)}")
        print(f"   ✅ Successful: {total_successful}")
        print(f"   ❌ Failed: {total_failed}")
        print(f"   ⏱️  Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
        
        if total_successful > 0:
            print(f"   📈 Average time per image: {total_time/total_successful:.1f}s")
        
        # Verify results in MongoDB
        print("\n🔍 Verifying results...")
        
        final_s3_count = await async_db.events.count_documents({
            'images.generation_method': 'dalle3_with_s3'
        })
        
        new_images = final_s3_count - initial_s3_count
        print(f"   📸 New S3 images created: {new_images}")
        
        # Show some examples
        print("\n📸 Sample generated images:")
        samples = await async_db.events.find({
            'images.generation_method': 'dalle3_with_s3'
        }).sort('images.generated_at', -1).limit(5).to_list(None)
        
        for sample in samples:
            print(f"\n   • {sample.get('name', 'Unnamed')[:50]}")
            print(f"     {sample['images']['ai_generated']}")
        
        # Check remaining active events
        remaining = await async_db.events.count_documents({
            "status": "active",
            "images.needs_regeneration": True
        })
        print(f"\n📊 Active events still needing images: {remaining}")
        
        await async_client.close()
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up temp env file
        try:
            os.remove(env_path)
        except:
            pass
        
        sync_client.close()
        
        if shutdown_requested:
            print("\n⚠️  Shutdown completed gracefully")

if __name__ == "__main__":
    # Get batch count from command line or use default
    batch_count = 50
    if len(sys.argv) > 1:
        try:
            batch_count = int(sys.argv[1])
        except:
            pass
    
    asyncio.run(generate_images(batch_count))