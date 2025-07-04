#!/usr/bin/env python3
"""
Check Algolia index settings and facets directly
"""

import os
import asyncio
from algoliasearch.search.client import SearchClient

async def check_algolia_facets():
    # Set environment variables
    app_id = "2VIXVMXHL7"
    api_key = "05ffc36eb256c9cb524ffb9293720ac2"
    index_name = "dxb_events"
    
    print("🔍 Checking Algolia Index Configuration")
    print("=" * 50)
    
    try:
        # Initialize client
        client = SearchClient(app_id, api_key)
        
        # Get index settings
        print("📋 Getting index settings...")
        settings_response = await client.get_settings(index_name=index_name)
        
        # Handle v4 API response format
        if hasattr(settings_response, 'actual_instance'):
            settings = settings_response.actual_instance
        else:
            settings = settings_response
            
        print("\n🔧 Current Index Settings:")
        print(f"✅ Searchable Attributes: {getattr(settings, 'searchableAttributes', None) or getattr(settings, 'searchable_attributes', [])}")
        print(f"✅ Attributes for Faceting: {getattr(settings, 'attributesForFaceting', None) or getattr(settings, 'attributes_for_faceting', [])}")
        print(f"✅ Numeric Attributes: {getattr(settings, 'numericAttributesForFiltering', None) or getattr(settings, 'numeric_attributes_for_filtering', [])}")
        
        # Test search with facets
        print("\n🧪 Testing search with facet counts...")
        search_result = await client.search(
            index_name=index_name,
            search_params={
                'query': 'kids',
                'facets': ['category', 'venue_area', 'is_free', 'family_friendly', 'price_tier'],
                'maxValuesPerFacet': 10
            }
        )
        
        # Handle v4 API response format
        if hasattr(search_result, 'actual_instance'):
            result = search_result.actual_instance
        else:
            result = search_result
        
        # Convert to dict if needed
        if hasattr(result, '__dict__'):
            result_dict = result.__dict__
        else:
            result_dict = result
            
        print(f"\n📊 Search Results:")
        print(f"   Total hits: {result_dict.get('nbHits', 0)}")
        print(f"   Processing time: {result_dict.get('processingTimeMS', 0)}ms")
        
        facets = result_dict.get('facets', {})
        print(f"\n🏷️ Actual Facet Counts:")
        for facet_name, facet_values in facets.items():
            print(f"   {facet_name}:")
            for value, count in list(facet_values.items())[:5]:  # Show top 5
                print(f"     - {value}: {count}")
        
        # Check a few sample records
        print(f"\n📄 Sample Records:")
        hits = result_dict.get('hits', [])
        for i, hit in enumerate(hits[:3]):
            hit_dict = hit.__dict__ if hasattr(hit, '__dict__') else hit
            print(f"   Record {i+1}:")
            print(f"     - Title: {hit_dict.get('title', 'N/A')}")
            print(f"     - Category: {hit_dict.get('category', 'N/A')}")
            print(f"     - Family Friendly: {hit_dict.get('family_friendly', 'N/A')}")
            print(f"     - Is Free: {hit_dict.get('is_free', 'N/A')}")
            print(f"     - Venue Area: {hit_dict.get('venue_area', 'N/A')}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("This might be due to API permissions or network issues")

if __name__ == "__main__":
    asyncio.run(check_algolia_facets())