#!/usr/bin/env python3
"""
Re-index all events to Algolia with proper facet data
"""

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime
import certifi
import ssl
import aiohttp

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from algoliasearch.search.client import SearchClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create SSL context with certifi certificates
ssl_context = ssl.create_default_context(cafile=certifi.where())

async def reindex_events():
    """Re-index all events to Algolia"""
    
    # Load environment variables
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / 'Backend.env'
    mongo_env_path = Path(__file__).parent.parent / 'Mongo.env'
    load_dotenv(env_path)
    load_dotenv(mongo_env_path)
    
    # Get credentials
    app_id = os.environ.get('ALGOLIA_APP_ID')
    api_key = os.environ.get('ALGOLIA_API_KEY')
    index_name = os.environ.get('ALGOLIA_INDEX_NAME', 'dxb_events')
    mongo_uri = os.environ.get('MONGODB_URI')
    
    if not all([app_id, api_key, mongo_uri]):
        logger.error("❌ Missing required credentials")
        return False
    
    logger.info(f"🔧 Re-indexing events to Algolia index: {index_name}")
    
    try:
        # Initialize MongoDB client
        mongo_client = AsyncIOMotorClient(mongo_uri)
        db = mongo_client['dxb_events']
        
        # Create a custom HTTP session with SSL context
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        session = aiohttp.ClientSession(connector=connector)
        
        # Initialize Algolia client with custom session
        algolia_client = SearchClient(app_id, api_key, http_requester_options={'session': session})
        
        # First, clear the index to start fresh
        logger.info("🗑️  Clearing existing index...")
        await algolia_client.clear_objects(index_name=index_name)
        
        # Configure index settings with facets
        logger.info("⚙️  Configuring index settings...")
        settings = {
            'searchableAttributes': [
                'title',
                'description',
                'venue_name',
                'venue_area',
                'category',
                'tags',
                '_searchable_text'
            ],
            'attributesForFaceting': [
                'filterOnly(category)',
                'filterOnly(venue_area)',
                'filterOnly(is_free)',
                'filterOnly(family_friendly)',
                'filterOnly(is_weekend)',
                'filterOnly(price_tier)'
            ],
            'numericAttributesForFiltering': [
                'base_price',
                'start_timestamp',
                'end_timestamp',
                'weekday'
            ],
            'typoTolerance': True
        }
        
        await algolia_client.set_settings(
            index_name=index_name,
            index_settings=settings
        )
        
        # Get all events from MongoDB
        logger.info("📊 Fetching events from MongoDB...")
        events_cursor = db.events.find({})
        events = await events_cursor.to_list(length=None)
        logger.info(f"   Found {len(events)} events")
        
        # Import the prepare function from algolia_service
        from services.algolia_service import AlgoliaService
        service = AlgoliaService()
        
        # Prepare events for indexing
        logger.info("🔄 Preparing events for indexing...")
        algolia_docs = []
        for event in events:
            doc = service.prepare_event_for_indexing(event)
            algolia_docs.append(doc)
        
        # Index events in batches
        batch_size = 100
        total_indexed = 0
        
        for i in range(0, len(algolia_docs), batch_size):
            batch = algolia_docs[i:i + batch_size]
            await algolia_client.save_objects(
                index_name=index_name,
                objects=batch
            )
            total_indexed += len(batch)
            logger.info(f"   Indexed {total_indexed}/{len(algolia_docs)} events...")
        
        logger.info(f"✅ Successfully re-indexed {total_indexed} events!")
        
        # Close connections
        await session.close()
        mongo_client.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to re-index events: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main function"""
    await reindex_events()

if __name__ == "__main__":
    asyncio.run(main())