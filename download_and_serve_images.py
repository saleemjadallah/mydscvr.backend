#!/usr/bin/env python3
"""
Simple Image Download and Storage Script
Downloads AI images from temporary URLs and saves them locally to fix CORS issues
"""

import os
import asyncio
import aiohttp
import hashlib
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from dotenv import load_dotenv
from loguru import logger

# Configure logging
logger.add("image_download.log", rotation="10 MB", retention="3 days")

# Load environment from multiple possible locations
for env_file in ['Mongo.env', '../mydscvr-datacollection/Mongo.env', '/home/ubuntu/mydscvr-datacollection/Mongo.env']:
    if os.path.exists(env_file):
        load_dotenv(dotenv_path=env_file)
        print(f"✅ Loaded env from: {env_file}")
        break


async def download_and_store_image(temp_url: str, event_id: str, event_title: str) -> str:
    """Download image from temporary URL and save locally"""
    
    try:
        # Create filename based on event ID and URL hash
        url_hash = hashlib.md5(temp_url.encode()).hexdigest()[:8]
        filename = f"{event_id}_{url_hash}.png"
        
        # Ensure storage directory exists
        storage_dir = "./storage/images"
        os.makedirs(storage_dir, exist_ok=True)
        
        file_path = os.path.join(storage_dir, filename)
        
        # Download image
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(temp_url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    
                    # Save to local file
                    with open(file_path, 'wb') as f:
                        f.write(image_data)
                    
                    # Return backend URL
                    backend_url = f"https://mydscvr.xyz/images/{filename}"
                    logger.info(f"✅ Downloaded and saved: {event_title} -> {backend_url}")
                    return backend_url
                else:
                    logger.error(f"❌ Failed to download {temp_url}: {response.status}")
                    return temp_url  # Return original if download fails
                    
    except Exception as e:
        logger.error(f"❌ Error downloading image for {event_title}: {str(e)}")
        return temp_url  # Return original if download fails


async def fix_cors_images():
    """Find events with AI images and download them locally"""
    
    print("🔧 Fixing CORS Issues - Downloading AI Images Locally")
    print("=" * 55)
    
    # Connect to MongoDB
    mongodb_uri = os.getenv('Mongo_URI')
    client = AsyncIOMotorClient(mongodb_uri)
    db = client['DXB']
    
    try:
        # Find events with OpenAI blob URLs (these have CORS issues)
        cursor = db.events.find({
            "image_url": {"$regex": "oaidalleapiprodscus.blob.core.windows.net"}
        }).limit(10)  # Start with 10 events
        
        events = await cursor.to_list(length=None)
        print(f"📊 Found {len(events)} events with OpenAI images to fix")
        
        success_count = 0
        
        for i, event in enumerate(events, 1):
            event_title = event.get('title', 'Unknown Event')
            event_id = str(event.get('_id'))
            temp_url = event.get('image_url')
            
            print(f"\n📥 {i}/{len(events)}: {event_title}")
            
            # Download and store locally
            new_url = await download_and_store_image(temp_url, event_id, event_title)
            
            if new_url != temp_url:  # Successfully downloaded
                # Update database with new URL
                result = await db.events.update_one(
                    {"_id": event['_id']},
                    {
                        "$set": {
                            "image_url": new_url,
                            "images.ai_generated": new_url,
                            "images.storage_type": "local_backend",
                            "images.cors_fixed": True
                        }
                    }
                )
                
                if result.modified_count > 0:
                    print(f"   ✅ Updated database: {new_url}")
                    success_count += 1
                else:
                    print(f"   ⚠️ Database update failed")
            else:
                print(f"   ❌ Download failed, keeping original URL")
        
        print(f"\n🎯 Complete! Fixed {success_count}/{len(events)} images")
        print("   Images are now served from backend and will work without CORS issues!")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        logger.error(f"Error in fix_cors_images: {str(e)}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(fix_cors_images()) 