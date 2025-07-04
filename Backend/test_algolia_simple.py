#!/usr/bin/env python3
"""
Simple Algolia connection test with SSL bypass
"""

import os
import ssl
import asyncio
import aiohttp
from algoliasearch.search.client import SearchClient

async def test_algolia_simple():
    # Set environment variables
    os.environ['ALGOLIA_APP_ID'] = '2VIXVMXHL7'
    os.environ['ALGOLIA_API_KEY'] = '05ffc36eb256c9cb524ffb9293720ac2'
    
    print("🧪 Testing Algolia Connection (Simple)")
    print("=" * 40)
    
    # Create SSL context that bypasses certificate verification
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        # Initialize client with basic configuration
        client = SearchClient(
            app_id='2VIXVMXHL7',
            api_key='05ffc36eb256c9cb524ffb9293720ac2'
        )
        
        print("✅ Algolia client initialized")
        
        # Test with simple object
        test_object = {
            'objectID': 'test_123',
            'title': 'Test Event',
            'description': 'This is a test event',
            'category': 'test'
        }
        
        print("📤 Testing object indexing...")
        
        # Index the object
        response = await client.save_objects(
            index_name='dxb_events',
            objects=[test_object]
        )
        
        print(f"✅ Object indexed successfully: {response}")
        
        # Wait a moment for indexing
        await asyncio.sleep(2)
        
        # Test search
        print("🔍 Testing search...")
        
        search_response = await client.search(
            search_method_params={
                "requests": [{
                    "indexName": "dxb_events",
                    "query": "test",
                    "hitsPerPage": 5
                }]
            }
        )
        
        print(f"✅ Search successful")
        print(f"Results: {search_response}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_algolia_simple())
    if success:
        print("\n✅ Algolia connection test passed!")
    else:
        print("\n❌ Algolia connection test failed")