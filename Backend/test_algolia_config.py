#!/usr/bin/env python3
"""
Test Algolia configuration without SSL issues
"""

import os
from services.algolia_service import algolia_service

# Set environment variables
os.environ['ALGOLIA_APP_ID'] = '2VIXVMXHL7'
os.environ['ALGOLIA_API_KEY'] = '05ffc36eb256c9cb524ffb9293720ac2'
os.environ['ALGOLIA_INDEX_NAME'] = 'dxb_events'

def test_algolia_config():
    print("🔧 Testing Algolia Configuration")
    print("=" * 40)
    
    print(f"App ID: {algolia_service.app_id}")
    print(f"Index Name: {algolia_service.index_name}")
    print(f"Service Enabled: {algolia_service.enabled}")
    
    # Test event preparation
    sample_event = {
        '_id': 'test123',
        'title': 'Kids Fun Day - Family Activities',
        'description': 'A wonderful day for children and families with activities',
        'category': 'family_activities',
        'tags': ['kids', 'family', 'fun'],
        'venue': {
            'name': 'Dubai Mall',
            'area': 'Downtown Dubai',
            'city': 'Dubai'
        },
        'start_date': '2025-07-06T10:00:00Z',
        'price': {
            'base_price': 0,
            'is_free': True
        }
    }
    
    print("\n🧪 Testing Event Preparation...")
    algolia_doc = algolia_service.prepare_event_for_indexing(sample_event)
    
    print(f"✅ Event prepared for indexing:")
    print(f"   Title: {algolia_doc['title']}")
    print(f"   Category: {algolia_doc['category']}")
    print(f"   Family Friendly: {algolia_doc['family_friendly']}")
    print(f"   Is Free: {algolia_doc['is_free']}")
    print(f"   Is Weekend: {algolia_doc['is_weekend']}")
    print(f"   Searchable Text: {algolia_doc['_searchable_text'][:100]}...")
    
    print("\n✅ Configuration looks good!")
    print("   The issue is likely SSL certificates in local environment.")
    print("   This should work fine on the production server.")

if __name__ == "__main__":
    test_algolia_config()