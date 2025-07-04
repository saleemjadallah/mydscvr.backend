#!/usr/bin/env python3
"""
Fix Algolia search to include facets
"""

import re

# Read the current algolia_service.py
with open('services/algolia_service.py', 'r') as f:
    content = f.read()

# Find the search_events method and add facets support
search_method_pattern = r'(search_params = \{[^}]+\})'

# Updated search params with facets
new_search_params = '''search_params = {
                "indexName": self.index_name,
                "query": query,
                "page": page - 1,  # Algolia pages are 0-indexed
                "hitsPerPage": per_page,
                "facets": [
                    "category",
                    "venue_area", 
                    "is_free",
                    "family_friendly",
                    "price_tier",
                    "is_weekend",
                    "weekday"
                ],
                "maxValuesPerFacet": 20
            }'''

# Add filters if they exist
facets_addition = '''
            
            # Add filters to search params
            if algolia_filter:
                search_params["filters"] = algolia_filter'''

# Replace the search params
content = re.sub(search_method_pattern, new_search_params + facets_addition, content)

# Also need to update the response parsing to include facets
response_pattern = r'(# Extract events and metadata[^}]+\})'

new_response = '''# Extract events and metadata
            result_data = response_data.get("results", [{}])[0] if response_data.get("results") else {}
            
            hits = result_data.get("hits", [])
            events = []
            for hit_data in hits:
                event_doc = hit_data
                event_doc['source_name'] = 'algolia'  # Mark as from Algolia
                events.append(event_doc)
            
            # Extract facets
            facets = result_data.get("facets", {})
            
            processing_time = datetime.now() - start_time
            
            return {
                "events": events,
                "total": result_data.get("nbHits", 0),
                "page": page,
                "per_page": per_page,
                "total_pages": max(1, -(-result_data.get("nbHits", 0) // per_page)),  # Ceiling division
                "has_next": page * per_page < result_data.get("nbHits", 0),
                "has_prev": page > 1,
                "suggestions": self.get_search_suggestions(query),
                "facets": facets,
                "processing_time_ms": int(processing_time.total_seconds() * 1000)
            }'''

# Replace the response section
content = re.sub(response_pattern, new_response, content, flags=re.DOTALL)

# Write the updated content
with open('services/algolia_service.py', 'w') as f:
    f.write(content)

print("✅ Updated algolia_service.py to include facets support")
print("📋 Added facets to search params:")
print("   - category, venue_area, is_free, family_friendly, price_tier")
print("   - is_weekend, weekday")
print("📤 Updated response to include facets data")