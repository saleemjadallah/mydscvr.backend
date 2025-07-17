#!/usr/bin/env python3
"""
Restore S3 image URLs from backup fields in MongoDB
"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv
import certifi
from datetime import datetime

load_dotenv('Backend.env')

def main():
    # Connect to MongoDB
    mongo_url = os.getenv('MONGODB_URL')
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client['DXB']
    events_collection = db['events']
    
    print("🔄 Restoring S3 Image URLs")
    print("=" * 50)
    
    # Step 1: Count events that have s3_url field
    print("\n📊 Step 1: Analyzing available image data")
    
    has_s3_url = events_collection.count_documents({'images.s3_url': {'$exists': True}})
    has_original_path = events_collection.count_documents({'images.original_local_path': {'$exists': True}})
    missing_ai_generated = events_collection.count_documents({'images.ai_generated': {'$exists': False}})
    
    print(f"Events with images.s3_url: {has_s3_url}")
    print(f"Events with images.original_local_path: {has_original_path}")
    print(f"Events missing images.ai_generated: {missing_ai_generated}")
    
    # Step 2: Restore ai_generated from s3_url where available
    print("\n🔧 Step 2: Restoring ai_generated field from s3_url")
    
    # First, restore from s3_url field
    result = events_collection.update_many(
        {
            'images.s3_url': {'$exists': True},
            'images.ai_generated': {'$exists': False}
        },
        [
            {
                '$set': {
                    'images.ai_generated': '$images.s3_url'
                }
            }
        ]
    )
    
    print(f"✅ Restored {result.modified_count} events from s3_url field")
    
    # Step 3: For events that already had ai_generated but it was cleared, check if it matches S3 pattern
    print("\n🔍 Step 3: Checking events that already have ai_generated field")
    
    # Count events with proper S3 URLs
    proper_s3_urls = events_collection.count_documents({
        'images.ai_generated': {'$regex': '^https://mydscvr-event-images.s3'}
    })
    
    print(f"Events with proper S3 URLs in ai_generated: {proper_s3_urls}")
    
    # Step 4: Verify unique images
    print("\n📊 Step 4: Analyzing image uniqueness")
    
    pipeline = [
        {'$match': {'images.ai_generated': {'$exists': True}}},
        {'$group': {
            '_id': '$images.ai_generated',
            'count': {'$sum': 1},
            'events': {'$push': '$name'}
        }},
        {'$match': {'count': {'$gt': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 10}
    ]
    
    duplicates = list(events_collection.aggregate(pipeline))
    
    if duplicates:
        print(f"\n⚠️  Found {len(duplicates)} duplicate images")
        print("\nTop duplicate images:")
        for dup in duplicates[:5]:
            print(f"  - {dup['count']} events using: {dup['_id'].split('/')[-1][:50]}")
            print(f"    Sample events: {', '.join(dup['events'][:3])}")
    else:
        print("\n✅ No duplicate images found!")
    
    # Step 5: Summary
    print("\n📈 Final Summary:")
    
    total_events = events_collection.count_documents({})
    events_with_images = events_collection.count_documents({'images.ai_generated': {'$exists': True}})
    events_without_images = total_events - events_with_images
    
    print(f"Total events: {total_events}")
    print(f"Events with AI images: {events_with_images}")
    print(f"Events without AI images: {events_without_images}")
    
    # Show sample restored images
    print("\n🖼️  Sample restored images:")
    samples = list(events_collection.find(
        {'images.ai_generated': {'$exists': True}},
        {'name': 1, 'images.ai_generated': 1}
    ).limit(5))
    
    for sample in samples:
        print(f"\n- {sample.get('name', 'Unnamed event')[:60]}")
        print(f"  URL: {sample['images']['ai_generated']}")
    
    print("\n✅ Restoration complete!")

if __name__ == "__main__":
    main()