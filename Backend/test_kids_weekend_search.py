#!/usr/bin/env python3
"""
Test script to verify the AI search optimization for combined queries like "kids weekend"
"""

import asyncio
import httpx
from datetime import datetime, timedelta
import json

async def test_search_queries():
    base_url = "http://localhost:8000/api/ai-search-v2"
    
    # Test queries
    test_queries = [
        "kids weekend",
        "family events this weekend",
        "free kids activities",
        "outdoor family fun this weekend",
        "children entertainment tomorrow",
        "weekend activities for kids"
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Testing AI Search Optimization for Kids/Family Events")
        print("=" * 60)
        
        for query in test_queries:
            print(f"\nTesting query: '{query}'")
            print("-" * 40)
            
            try:
                response = await client.get(
                    base_url,
                    params={"q": query, "per_page": 10}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Display AI response
                    print(f"AI Response: {data.get('ai_response', 'No AI response')}")
                    print(f"Total Events Found: {data['pagination']['total']}")
                    
                    # Check query analysis
                    analysis = data.get('query_analysis', {})
                    print(f"Time Period: {analysis.get('time_period', 'None')}")
                    print(f"Family Friendly: {analysis.get('family_friendly', 'None')}")
                    print(f"Keywords: {', '.join(analysis.get('keywords', []))}")
                    
                    # Check events
                    events = data.get('events', [])
                    if events:
                        print(f"\nFirst 3 events:")
                        for i, event in enumerate(events[:3], 1):
                            print(f"\n{i}. {event['title']}")
                            print(f"   Date: {event['start_date']} to {event['end_date']}")
                            print(f"   Category: {event.get('category', 'N/A')}")
                            print(f"   Family Score: {event.get('familyScore', 'N/A')}")
                            print(f"   Price: {event.get('price', 'N/A')}")
                            print(f"   Tags: {', '.join(event.get('tags', [])[:5])}")
                    else:
                        print("No events returned")
                    
                    # Display suggestions
                    suggestions = data.get('suggestions', [])
                    if suggestions:
                        print(f"\nSuggestions: {', '.join(suggestions[:3])}")
                    
                else:
                    print(f"Error: Status code {response.status_code}")
                    print(f"Response: {response.text}")
                    
            except Exception as e:
                print(f"Error testing query '{query}': {e}")
            
            print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(test_search_queries()) 