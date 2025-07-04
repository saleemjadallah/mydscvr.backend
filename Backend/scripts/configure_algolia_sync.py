#!/usr/bin/env python3
"""
Configure Algolia Index Settings (Synchronous Version)
"""

import os
import sys
import asyncio
from pathlib import Path
from algoliasearch.search.client import SearchClient

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def configure_algolia_index():
    """Configure Algolia index with proper settings and facets"""
    
    # Get credentials from environment
    app_id = os.environ.get('ALGOLIA_APP_ID')
    api_key = os.environ.get('ALGOLIA_API_KEY')
    index_name = os.environ.get('ALGOLIA_INDEX_NAME', 'dxb_events')
    
    if not app_id or not api_key:
        logger.error("❌ Missing Algolia credentials")
        return False
    
    logger.info(f"🔧 Configuring Algolia index: {index_name}")
    logger.info(f"   App ID: {app_id}")
    
    try:
        # Initialize Algolia client
        client = SearchClient(app_id, api_key)
        
        # Configure index settings
        settings = {
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
            ],
            'attributesForFaceting': [
                'filterOnly(category)',
                'filterOnly(primary_category)', 
                'filterOnly(venue_area)',
                'filterOnly(venue_city)',
                'filterOnly(is_free)',
                'filterOnly(family_friendly)',
                'filterOnly(price_tier)',
                'filterOnly(is_weekend)',
                'filterOnly(weekday)',
                'searchable(age_range)',
                'searchable(tags)',
                'filterOnly(source_name)'
            ],
            'numericAttributesForFiltering': [
                'base_price',
                'start_timestamp',
                'end_timestamp',
                'weekday',
                'family_score',
                'popularity_score',
                'quality_score'
            ],
            'customRanking': [
                'desc(popularity_score)',
                'desc(quality_score)',
                'asc(start_timestamp)'
            ],
            'attributesToSnippet': [
                'description:20'
            ],
            'snippetEllipsisText': '…',
            'highlightPreTag': '<em>',
            'highlightPostTag': '</em>',
            'typoTolerance': True,
            'minWordSizefor1Typo': 4,
            'minWordSizefor2Typos': 8
        }
        
        # Set index settings
        response = await client.set_settings(
            index_name=index_name,
            index_settings=settings
        )
        
        logger.info("✅ Algolia index settings configured successfully!")
        # The response structure may vary, so we'll just log success
        
        # Log configured features
        logger.info("\n📊 Configured Features:")
        logger.info("  ✓ Facets for filtering:")
        logger.info("    - category, venue_area, is_free, family_friendly")
        logger.info("    - price_tier, is_weekend, weekday")
        logger.info("  ✓ Numeric filters:")
        logger.info("    - base_price, timestamps, scores")
        logger.info("  ✓ Searchable attributes:")
        logger.info("    - title, description, venue info, tags")
        logger.info("  ✓ Typo tolerance enabled")
        logger.info("  ✓ Custom ranking by popularity and quality")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to configure Algolia: {e}")
        return False

async def main():
    """Main function"""
    # Load environment variables from Backend.env
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / 'Backend.env'
    load_dotenv(env_path)
    
    # Configure the index
    await configure_algolia_index()

if __name__ == "__main__":
    asyncio.run(main())