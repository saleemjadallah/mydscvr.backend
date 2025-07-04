#!/usr/bin/env python3
"""
Test Algolia connection and basic functionality
"""

import os
import asyncio
from services.algolia_service import AlgoliaService

async def test_algolia():
    # Set environment variables
    os.environ['ALGOLIA_APP_ID'] = '2VIXVMXHL7'
    os.environ['ALGOLIA_API_KEY'] = '05ffc36eb256c9cb524ffb9293720ac2'
    os.environ['ALGOLIA_SEARCH_API_KEY'] = 'f7cc9a0d4f419fdf84acfd6ad924059f'
    os.environ['ALGOLIA_INDEX_NAME'] = 'dxb_events'
    
    print("🧪 Testing Algolia Connection")
    print("=" * 40)
    
    # Initialize service
    algolia = AlgoliaService()
    
    if not algolia.enabled:
        print("❌ Algolia service not enabled")
        return False
    
    print(f"✅ Algolia service initialized")
    print(f"   App ID: {algolia.app_id}")
    print(f"   Index: {algolia.index_name}")
    
    # Test with sample event
    sample_event = {
        '_id': 'test123',
        'title': 'Kids Summer Camp',
        'description': 'Fun activities for children in Dubai Marina',
        'category': 'family_activities',
        'venue': {
            'name': 'Dubai Marina Mall',
            'area': 'Marina',
            'city': 'Dubai'
        },
        'price': {
            'base_price': 150,
            'is_free': False
        },
        'start_date': '2025-07-05T10:00:00',
        'end_date': '2025-07-05T16:00:00',
        'tags': ['kids', 'family', 'summer'],
        'family_score': 85,
        'is_family_friendly': True
    }
    
    print("\n📤 Testing event indexing...")
    success = await algolia.index_events([sample_event])
    
    if success:
        print("✅ Sample event indexed successfully")
    else:
        print("❌ Failed to index sample event")
        return False
    
    print("\n🔍 Testing search...")
    
    # Wait a moment for indexing
    import time
    time.sleep(2)
    
    # Test search
    result = await algolia.search_events("kids marina", page=1, per_page=5)
    
    print(f"Search results: {len(result['events'])} events found")
    print(f"Total: {result['total']}")
    print(f"Processing time: {result['processing_time_ms']}ms")
    
    if result['events']:
        event = result['events'][0]
        print(f"First result: {event['title']}")
    
    print("\n🎉 Algolia test completed successfully!")
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(test_algolia())
        if success:
            print("\n✅ Algolia is ready to use!")
        else:
            print("\n❌ Algolia test failed")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()