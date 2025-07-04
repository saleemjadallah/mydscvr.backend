#!/usr/bin/env python3
"""
Reconfigure Algolia index specifically for facets visibility in dashboard
"""

import os
import asyncio
from algoliasearch.search.client import SearchClient

async def reconfigure_facets():
    # Set environment variables
    app_id = "2VIXVMXHL7"
    api_key = "05ffc36eb256c9cb524ffb9293720ac2"
    index_name = "dxb_events"
    
    print("🔧 Reconfiguring Algolia Facets for Dashboard Visibility")
    print("=" * 60)
    
    try:
        # Initialize client
        client = SearchClient(app_id, api_key)
        
        # Configure settings specifically for facets
        settings = {
            'attributesForFaceting': [
                'searchable(category)',
                'searchable(venue_area)',
                'searchable(venue_city)',
                'filterOnly(is_free)',
                'filterOnly(family_friendly)',
                'searchable(price_tier)',
                'filterOnly(is_weekend)',
                'filterOnly(weekday)',
                'searchable(age_range)',
                'searchable(tags)',
                'filterOnly(source_name)'
            ],
            'searchableAttributes': [
                'title',
                'description', 
                'venue_name',
                'venue_area',
                'venue_city',
                'category',
                'primary_category',
                'tags',
                'age_range',
                'location',
                '_searchable_text'
            ]
        }
        
        print("⚙️ Setting facet configuration...")
        await client.set_settings(
            index_name=index_name,
            index_settings=settings
        )
        
        print("✅ Facet configuration updated!")
        
        # Test a search to make sure facets are returned
        print("\n🧪 Testing facet retrieval...")
        search_result = await client.search(
            search_method_params={
                "requests": [{
                    "indexName": index_name,
                    "query": "kids",
                    "facets": ["category", "venue_area", "is_free", "family_friendly"],
                    "maxValuesPerFacet": 10
                }]
            }
        )
        
        if hasattr(search_result, 'results') and search_result.results:
            result = search_result.results[0]
            
            # Try to access facets
            if hasattr(result, 'facets'):
                facets = result.facets
                print(f"✅ Facets found: {list(facets.keys()) if facets else 'None'}")
                
                if facets:
                    for facet_name, values in facets.items():
                        print(f"   {facet_name}: {dict(list(values.items())[:3])}")
                else:
                    print("⚠️ Facets object exists but is empty")
            else:
                print("⚠️ No facets found in search result")
                print(f"   Available attributes: {dir(result)}")
        
        print(f"\n🎯 Next Steps:")
        print(f"   1. Check your Algolia dashboard at: https://www.algolia.com/apps/{app_id}/explorer/browse/{index_name}")
        print(f"   2. Go to Configuration > Facets to see the facets")
        print(f"   3. The facets should now be visible for dashboard configuration")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(reconfigure_facets())