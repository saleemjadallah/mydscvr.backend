#!/usr/bin/env python3
"""
Fix duplicate S3 images issue by ensuring each event has a unique AI-generated image
"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime
import certifi
from collections import Counter

load_dotenv('Backend.env')

def main():
    # Connect to MongoDB with SSL
    mongo_url = os.getenv('MONGODB_URL')
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client['DXB']
    events_collection = db['events']
    
    print("🚀 Fixing Duplicate S3 Images")
    print("=" * 50)
    
    # Step 1: Analyze current state
    print("\n📊 Step 1: Analyzing current image distribution")
    
    all_events = list(events_collection.find({}, {'_id': 1, 'event_id': 1, 'name': 1, 'title': 1, 'images': 1}))
    print(f"Total events: {len(all_events)}")
    
    # Count image usage
    image_usage = Counter()
    events_by_image = {}
    events_without_images = []
    
    for event in all_events:
        images = event.get('images', {})
        if isinstance(images, dict) and images.get('ai_generated'):
            image_url = images['ai_generated']
            image_usage[image_url] += 1
            if image_url not in events_by_image:
                events_by_image[image_url] = []
            events_by_image[image_url].append(event)
        else:
            events_without_images.append(event)
    
    print(f"Events with AI images: {sum(image_usage.values())}")
    print(f"Events without AI images: {len(events_without_images)}")
    print(f"Unique images: {len(image_usage)}")
    
    # Find duplicates
    duplicates = {img: count for img, count in image_usage.items() if count > 1}
    print(f"\nDuplicate images found: {len(duplicates)}")
    
    if duplicates:
        print("\nTop 10 most duplicated images:")
        for img, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {count} events using: {img.split('/')[-1]}")
    
    # Step 2: Fix data model - ensure all events have names
    print("\n🔧 Step 2: Fixing event names")
    
    events_without_names = events_collection.count_documents({'name': {'$exists': False}})
    if events_without_names > 0:
        # Copy title to name field
        result = events_collection.update_many(
            {'name': {'$exists': False}},
            [{'$set': {'name': {'$ifNull': ['$title', 'Untitled Event']}}}]
        )
        print(f"✅ Added 'name' field to {result.modified_count} events")
    else:
        print("✅ All events already have names")
    
    # Step 3: Mark duplicate images for regeneration
    print("\n🔄 Step 3: Marking duplicate images for regeneration")
    
    events_to_regenerate = []
    
    # For each duplicate image, keep the first event and mark others for regeneration
    for image_url, events in events_by_image.items():
        if len(events) > 1:
            # Keep the first event, regenerate others
            for event in events[1:]:
                events_to_regenerate.append(event['_id'])
    
    # Also add events without images
    for event in events_without_images:
        events_to_regenerate.append(event['_id'])
    
    print(f"Events marked for regeneration: {len(events_to_regenerate)}")
    
    if events_to_regenerate:
        # Mark these events for regeneration
        result = events_collection.update_many(
            {'_id': {'$in': events_to_regenerate}},
            {
                '$set': {
                    'images.needs_regeneration': True,
                    'images.marked_at': datetime.utcnow()
                }
            }
        )
        print(f"✅ Marked {result.modified_count} events for AI image regeneration")
        
        # Clear the ai_generated field for these events to force regeneration
        result = events_collection.update_many(
            {'_id': {'$in': events_to_regenerate}},
            {
                '$unset': {'images.ai_generated': ''}
            }
        )
        print(f"✅ Cleared ai_generated field for {result.modified_count} events")
    
    # Step 4: Verify fix
    print("\n✅ Step 4: Verifying fix")
    
    # Re-count after fix
    remaining_duplicates = 0
    image_usage_after = Counter()
    
    for event in events_collection.find({'images.ai_generated': {'$exists': True}}, {'images.ai_generated': 1}):
        image_url = event['images']['ai_generated']
        image_usage_after[image_url] += 1
    
    remaining_duplicates = sum(1 for count in image_usage_after.values() if count > 1)
    
    print(f"\nRemaining duplicate images: {remaining_duplicates}")
    print(f"Events needing AI generation: {len(events_to_regenerate)}")
    
    print("\n🎉 Fix complete!")
    print("\nNext steps:")
    print("1. The DataCollection service will generate unique images for marked events")
    print("2. Ensure the DataCollection service uses unique prompts based on event details")
    print("3. Monitor the 'needs_regeneration' flag to track progress")

if __name__ == "__main__":
    main()