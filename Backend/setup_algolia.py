#!/usr/bin/env python3
"""
Algolia Search Setup Script
Run this script to set up Algolia search for your DXB Events platform
"""

import os
import sys
import asyncio
from services.algolia_service import algolia_service
from database import init_databases, get_mongodb

async def setup_algolia():
    """
    Set up Algolia search index with your events data
    """
    print("🚀 Setting up Algolia Search for DXB Events")
    print("=" * 50)
    
    # Check environment variables
    required_vars = ['ALGOLIA_APP_ID', 'ALGOLIA_API_KEY']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these environment variables and try again.")
        print("\nTo get Algolia credentials:")
        print("1. Sign up at https://www.algolia.com/")
        print("2. Create a new application")
        print("3. Go to Settings > Team and Access > API Keys")
        print("4. Copy your Application ID and Admin API Key")
        print("\nExample:")
        print(f"export ALGOLIA_APP_ID='your_app_id'")
        print(f"export ALGOLIA_API_KEY='your_admin_api_key'")
        return False
    
    if not algolia_service.enabled:
        print("❌ Algolia service failed to initialize")
        return False
    
    print(f"✅ Algolia service initialized")
    print(f"   App ID: {algolia_service.app_id}")
    print(f"   Index: {algolia_service.index_name}")
    
    # Initialize database
    print("\n📊 Connecting to MongoDB...")
    try:
        await init_databases()
        db = await get_mongodb()
        print("✅ MongoDB connected")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        return False
    
    # Fetch events to index
    print("\n📥 Fetching events from database...")
    try:
        events_cursor = db.events.find({"status": "active"}).limit(1000)
        events = await events_cursor.to_list(length=1000)
        print(f"✅ Found {len(events)} events to index")
        
        if len(events) == 0:
            print("⚠️ No events found in database. Make sure you have events data.")
            return False
            
    except Exception as e:
        print(f"❌ Failed to fetch events: {e}")
        return False
    
    # Index events to Algolia
    print("\n🔍 Indexing events to Algolia...")
    try:
        success = await algolia_service.index_events(events)
        if success:
            print(f"✅ Successfully indexed {len(events)} events")
        else:
            print("❌ Failed to index events")
            return False
    except Exception as e:
        print(f"❌ Indexing failed: {e}")
        return False
    
    # Configure index settings
    print("\n⚙️ Configuring index settings...")
    try:
        await algolia_service.configure_index_settings()
        print("✅ Index settings configured")
    except Exception as e:
        print(f"❌ Failed to configure settings: {e}")
        return False
    
    print("\n🎉 Algolia Search Setup Complete!")
    print("=" * 50)
    print("\nYour search endpoints are now available:")
    print(f"• Search: GET /api/algolia-search?q=kids+activities")
    print(f"• Status: GET /api/algolia-search/status")
    print(f"• Suggestions: GET /api/algolia-search/suggest?q=kid")
    print(f"• Facets: GET /api/algolia-search/facets")
    
    print("\nFeatures enabled:")
    print("✅ Instant search (< 100ms)")
    print("✅ Typo tolerance")
    print("✅ Intelligent ranking")
    print("✅ Advanced filtering")
    print("✅ Auto-suggestions")
    print("✅ Search highlighting")
    
    print("\nTo test the search:")
    print("curl 'http://localhost:8000/api/algolia-search?q=kids+weekend'")
    
    return True

def print_help():
    """Print usage help"""
    print("Algolia Search Setup for DXB Events")
    print("\nUsage:")
    print("  python setup_algolia.py")
    print("\nEnvironment Variables Required:")
    print("  ALGOLIA_APP_ID     - Your Algolia Application ID")
    print("  ALGOLIA_API_KEY    - Your Algolia Admin API Key")
    print("\nOptional:")
    print("  ALGOLIA_INDEX_NAME - Index name (default: dxb_events)")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print_help()
        sys.exit(0)
    
    try:
        success = asyncio.run(setup_algolia())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)