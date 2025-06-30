#!/usr/bin/env python3
"""
Test the improved deduplication logic
Test with the existing Shreya Ghoshal duplicates to see if it catches them
"""

import os
import sys
import asyncio
from datetime import datetime

# Add backend path for deduplication
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Backend'))

from perplexity_storage import PerplexityEventsStorage
from motor.motor_asyncio import AsyncIOMotorClient
from utils.deduplication import EventDeduplicator

async def test_deduplication():
    """Test the improved deduplication logic"""
    
    # Connect to MongoDB
    mongodb_uri = os.getenv('Mongo_URI')
    if not mongodb_uri:
        print("❌ MongoDB URI not found")
        return
    
    client = AsyncIOMotorClient(mongodb_uri, tlsInsecure=True)
    db = client['DXB']
    
    try:
        # Initialize deduplicator
        deduplicator = EventDeduplicator(db)
        
        print("🔍 Testing improved deduplication logic...")
        
        # Get the two Shreya Ghoshal events
        shreya_events = await db.events.find({"title": "Shreya Ghoshal Live in Dubai"}).to_list(length=None)
        
        if len(shreya_events) < 2:
            print(f"⚠️ Found only {len(shreya_events)} Shreya Ghoshal events. Need at least 2 for testing.")
            return
        
        print(f"✅ Found {len(shreya_events)} Shreya Ghoshal events:")
        for i, event in enumerate(shreya_events):
            print(f"  {i+1}. ID: {event['_id']}")
            print(f"     Time: {event.get('start_date', 'Unknown')}")
            print(f"     Venue: {event.get('venue', {}).get('name', 'Unknown')}")
            print()
        
        # Test if first event would be detected as duplicate of second
        event1 = shreya_events[0]
        event2 = shreya_events[1]
        
        print("🧪 Testing deduplication logic:")
        
        # Calculate title similarity directly
        title_similarity = deduplicator._calculate_text_similarity(
            event1.get("title", ""),
            event2.get("title", "")
        )
        
        print(f"📊 Title similarity: {title_similarity:.2%}")
        print(f"📏 Threshold: 85%")
        
        # Test if it would be detected as duplicate
        would_be_duplicate = title_similarity >= 0.85
        print(f"🎯 Would be detected as duplicate: {'✅ YES' if would_be_duplicate else '❌ NO'}")
        
        if would_be_duplicate:
            print("✅ IMPROVED LOGIC WORKS! These duplicates would now be caught and merged.")
        else:
            print("❌ Still not working. Title similarity too low.")
        
        # Test the actual duplicate detection
        print("\n🔄 Testing actual duplicate detection...")
        candidates = await deduplicator._get_duplicate_candidates(event1)
        print(f"📋 Found {len(candidates)} candidates for duplicate check")
        
        for candidate in candidates:
            if candidate['_id'] == event2['_id']:
                print("✅ Existing duplicate found in candidates!")
                break
        else:
            print("❌ Existing duplicate NOT found in candidates")
        
        print("\n🎉 Test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()

async def test_similarity_calculation():
    """Test similarity calculation with various title pairs"""
    
    client = AsyncIOMotorClient(os.getenv('Mongo_URI'), tlsInsecure=True)
    db = client['DXB']
    deduplicator = EventDeduplicator(db)
    
    test_cases = [
        ("Shreya Ghoshal Live in Dubai", "Shreya Ghoshal Live in Dubai"),
        ("La Perle by Dragone", "La Perle by Dragone at Al Habtoor City"),
        ("Dubai Summer Surprises", "Dubai Summer Surprises (DSS)"),
        ("ToDA - 9D Breathwork Meditation", "ToDA 9D Breathwork Meditation"),
        ("Ladies Night at Malibu", "Malibu Ladies Night"),
        ("Completely Different Event", "Another Totally Different Show")
    ]
    
    print("🧮 Testing similarity calculations:")
    print("=" * 60)
    
    for title1, title2 in test_cases:
        similarity = deduplicator._calculate_text_similarity(title1, title2)
        would_merge = similarity >= 0.85
        
        print(f"Title 1: '{title1}'")
        print(f"Title 2: '{title2}'") 
        print(f"Similarity: {similarity:.2%} | Would merge: {'✅ YES' if would_merge else '❌ NO'}")
        print("-" * 60)
    
    client.close()

if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'Mongo.env'))
    
    print("🔧 Testing Improved Deduplication Logic")
    print("=" * 50)
    
    # Run tests
    asyncio.run(test_deduplication())
    print()
    asyncio.run(test_similarity_calculation())