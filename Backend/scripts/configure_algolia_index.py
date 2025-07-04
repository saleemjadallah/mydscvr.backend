#!/usr/bin/env python3
"""
Configure Algolia Index Settings
This script configures the Algolia index with proper facets and settings
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from services.algolia_service import algolia_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def configure_algolia_index():
    """Configure Algolia index with proper settings and facets"""
    
    if not algolia_service.enabled:
        logger.error("❌ Algolia is not enabled. Please check your environment variables.")
        logger.info("Required environment variables:")
        logger.info("  - ALGOLIA_APP_ID")
        logger.info("  - ALGOLIA_API_KEY")
        logger.info("  - ALGOLIA_INDEX_NAME (optional, defaults to 'dxb_events')")
        return False
    
    logger.info(f"🔧 Configuring Algolia index: {algolia_service.index_name}")
    
    # Configure index settings
    success = await algolia_service.configure_index_settings()
    
    if success:
        logger.info("✅ Algolia index configuration complete!")
        logger.info("\nConfigured facets:")
        logger.info("  - category (filter only)")
        logger.info("  - venue_area (filter only)")
        logger.info("  - is_free (filter only)")
        logger.info("  - family_friendly (filter only)")
        logger.info("  - price_tier (filter only)")
        logger.info("  - is_weekend (filter only)")
        logger.info("  - weekday (filter only)")
        logger.info("  - age_range (searchable)")
        logger.info("  - tags (searchable)")
        logger.info("\nConfigured numeric filters:")
        logger.info("  - base_price")
        logger.info("  - start_timestamp")
        logger.info("  - end_timestamp")
        logger.info("  - weekday")
        logger.info("\nSearchable attributes:")
        logger.info("  - title")
        logger.info("  - description")
        logger.info("  - venue_name")
        logger.info("  - venue_area")
        logger.info("  - category")
        logger.info("  - tags")
        logger.info("  - _searchable_text")
    else:
        logger.error("❌ Failed to configure Algolia index")
        return False
    
    return True

async def main():
    """Main function"""
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Configure the index
    await configure_algolia_index()

if __name__ == "__main__":
    asyncio.run(main())