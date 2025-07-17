#!/usr/bin/env python3
"""
Permanently remove all duplicate AI-generated images from MongoDB
Keep only one instance of each unique image
"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv
import certifi
from collections import defaultdict
from datetime import datetime

load_dotenv('Backend.env')

def main():
    # Connect to MongoDB
    mongo_url = os.getenv('MONGODB_URL')
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client['DXB']
    events_collection = db['events']
    
    print("🧹 Permanently Removing Duplicate Images")
    print("=" * 50)
    
    # Step 1: Analyze current duplicates
    print("\n📊 Step 1: Analyzing duplicate images")
    
    # Group events by their AI-generated image URL
    image_to_events = defaultdict(list)
    
    all_events = list(events_collection.find(
        {'images.ai_generated': {'$exists': True}},
        {'_id': 1, 'name': 1, 'title': 1, 'images.ai_generated': 1, 'category': 1}
    ))
    
    for event in all_events:
        image_url = event.get('images', {}).get('ai_generated')
        if image_url:
            image_to_events[image_url].append(event)
    
    # Find duplicates
    duplicate_images = {img: events for img, events in image_to_events.items() if len(events) > 1}
    unique_images = {img: events for img, events in image_to_events.items() if len(events) == 1}
    
    print(f"Total unique image URLs: {len(image_to_events)}")
    print(f"Images used by only 1 event: {len(unique_images)}")
    print(f"Images used by multiple events: {len(duplicate_images)}")
    
    # Show worst offenders
    if duplicate_images:
        print("\nTop 5 most duplicated images:")
        sorted_dups = sorted(duplicate_images.items(), key=lambda x: len(x[1]), reverse=True)[:5]
        for img_url, events in sorted_dups:
            print(f"\n  Image: {img_url.split('/')[-1][:50]}...")
            print(f"  Used by {len(events)} events")
            print(f"  Sample events: {', '.join([e.get('name') or e.get('title', 'Unnamed')[:30] for e in events[:3]])}...")
    
    # Step 2: Clear ai_generated field from all events with duplicate images
    print("\n🔄 Step 2: Removing duplicate images from events")
    
    events_to_clear = []
    kept_count = 0
    
    for image_url, events in duplicate_images.items():
        # Sort events by category diversity to keep the most relevant one
        # Prefer events with names over those without
        sorted_events = sorted(events, 
                             key=lambda e: (
                                 1 if e.get('name') else 0,  # Has name
                                 1 if e.get('category') else 0,  # Has category
                                 len(e.get('title', ''))  # Longer title
                             ), 
                             reverse=True)
        
        # Keep the first (best) event, clear the rest
        events_to_clear.extend([e['_id'] for e in sorted_events[1:]])
        kept_count += 1
    
    print(f"\nKeeping image for {kept_count} events (best match for each image)")
    print(f"Clearing images from {len(events_to_clear)} events")
    
    if events_to_clear:
        # Clear the ai_generated field from duplicate events
        result = events_collection.update_many(
            {'_id': {'$in': events_to_clear}},
            {
                '$unset': {'images.ai_generated': ''},
                '$set': {
                    'images.needs_regeneration': True,
                    'images.cleared_duplicate_at': datetime.utcnow(),
                    'images.status': 'duplicate_removed'
                }
            }
        )
        print(f"✅ Cleared duplicate images from {result.modified_count} events")
    
    # Step 3: Verify the cleanup
    print("\n✅ Step 3: Verifying cleanup")
    
    # Re-analyze after cleanup
    remaining_duplicates = []
    pipeline = [
        {'$match': {'images.ai_generated': {'$exists': True}}},
        {'$group': {
            '_id': '$images.ai_generated',
            'count': {'$sum': 1}
        }},
        {'$match': {'count': {'$gt': 1}}}
    ]
    
    remaining_duplicates = list(events_collection.aggregate(pipeline))
    
    # Final statistics
    total_events = events_collection.count_documents({})
    with_images = events_collection.count_documents({'images.ai_generated': {'$exists': True}})
    needs_regen = events_collection.count_documents({'images.needs_regeneration': True})
    
    print(f"\nFinal Statistics:")
    print(f"Total events: {total_events}")
    print(f"Events with unique AI images: {with_images}")
    print(f"Events needing image regeneration: {needs_regen}")
    print(f"Remaining duplicate images: {len(remaining_duplicates)}")
    
    # Show some events that kept their images
    print("\n🖼️  Sample events with unique images:")
    samples = list(events_collection.find(
        {'images.ai_generated': {'$exists': True}},
        {'name': 1, 'title': 1, 'category': 1, 'images.ai_generated': 1}
    ).limit(10))
    
    for sample in samples:
        name = sample.get('name') or sample.get('title', 'Unnamed')
        category = sample.get('category', 'uncategorized')
        image_name = sample['images']['ai_generated'].split('/')[-1][:40]
        print(f"\n- {name[:50]} ({category})")
        print(f"  Image: .../{image_name}...")
    
    print("\n🎯 Duplicate removal complete!")
    print(f"\n📝 Next steps:")
    print(f"1. {needs_regen} events need AI image regeneration")
    print(f"2. Run the DataCollection service to generate unique images")
    print(f"3. Ensure each event has unique identifiers for better prompts")

if __name__ == "__main__":
    main()