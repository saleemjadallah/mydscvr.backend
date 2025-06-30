#!/usr/bin/env python3
"""
Firecrawl-only test extraction
Test just the Firecrawl MCP phase with sophisticated prompts
"""

import asyncio
import json
import os
from firecrawl_mcp_extractor import FirecrawlMCPExtractor
from perplexity_storage import PerplexityEventsStorage
from loguru import logger

async def collect_firecrawl_only():
    try:
        storage = PerplexityEventsStorage()
        
        logger.info('🔥 Starting Firecrawl-ONLY extraction test...')
        
        # Phase 2: Firecrawl MCP extraction ONLY
        firecrawl_events = []
        
        try:
            logger.info('🔥 Phase 2: Firecrawl MCP supplemental extraction')
            firecrawl_extractor = FirecrawlMCPExtractor()
            
            # Get daily limits from environment
            firecrawl_limits = {
                'platinumlist': int(os.getenv('FIRECRAWL_PLATINUMLIST_LIMIT', '25')),
                'timeout': int(os.getenv('FIRECRAWL_TIMEOUT_LIMIT', '15')),
                'whatson': int(os.getenv('FIRECRAWL_WHATSON_LIMIT', '10'))
            }
            
            logger.info(f'🎯 Firecrawl limits: {firecrawl_limits}')
            
            firecrawl_results = await firecrawl_extractor.extract_all_sources(firecrawl_limits)
            
            # Flatten Firecrawl results
            for source, events in firecrawl_results.items():
                firecrawl_events.extend(events)
                logger.info(f'🔥 {source}: {len(events)} events')
            
            logger.info(f'📊 Firecrawl Phase 2 completed: {len(firecrawl_events)} events')
            
            # Ensure Firecrawl extractor is properly cleaned up
            del firecrawl_extractor
            
        except Exception as e:
            logger.error(f'❌ Firecrawl extraction failed: {e}')
            logger.error(f'❌ Firecrawl error details: {str(e)}')
            import traceback
            logger.error(f'❌ Full traceback: {traceback.format_exc()}')
            firecrawl_events = []
        
        # Log final summary
        logger.info(f'🎯 FIRECRAWL-ONLY extraction summary:')
        logger.info(f'   🔥 Firecrawl: {len(firecrawl_events)} events')
        logger.info(f'🛑 FIRECRAWL EXTRACTION COMPLETED - Starting storage phase')
        
        if firecrawl_events:
            # Create extraction session
            session_id = storage.create_extraction_session('firecrawl_only_test')
            logger.info(f'📝 Created session: {session_id}')
            
            # Store events one by one to identify exact issue
            stored_count = 0
            for i, event in enumerate(firecrawl_events):
                try:
                    # Verify event is a dictionary
                    if not isinstance(event, dict):
                        logger.error(f"❌ Event {i} is not a dict: {type(event)}")
                        continue
                    
                    # Store single event with deduplication
                    result = await storage.store_events([event], session_id)
                    
                    if result.get('stored_count', 0) > 0:
                        stored_count += 1
                        logger.info(f"✅ Stored Firecrawl event {stored_count}: {event.get('title', 'No title')[:50]}...")
                    else:
                        logger.info(f"⚠️ Skipped duplicate: {event.get('title', 'No title')[:50]}...")
                    
                except Exception as e:
                    logger.error(f"❌ Error storing event {i}: {e}")
                    continue
            
            logger.info(f"✅ Successfully stored {stored_count} out of {len(firecrawl_events)} Firecrawl events")
            
            # Update session
            session_update = {
                'total_events': len(firecrawl_events),
                'stored_events': stored_count,
                'status': 'completed',
                'extraction_method': 'firecrawl_only_test',
                'firecrawl_events': len(firecrawl_events),
                'firecrawl_enabled': True
            }
            
            storage.update_extraction_session(session_id, session_update)
            
            logger.info(f'🏁 FIRECRAWL-ONLY TEST COMPLETED SUCCESSFULLY')
            logger.info(f'📊 Final Summary:')
            logger.info(f'   🔥 Firecrawl events extracted: {len(firecrawl_events)}')
            logger.info(f'   💾 Unique events stored: {stored_count}')
            
            # Show sample events
            if stored_count > 0:
                logger.info(f'📋 Sample Firecrawl events stored:')
                recent_events = firecrawl_events[:3]
                for i, event in enumerate(recent_events):
                    title = event.get('title', 'No title')
                    source = event.get('extraction_source', 'Unknown')
                    family_score = event.get('family_score', 0)
                    logger.info(f'   {i+1}. {title} | {source} | Family: {family_score}')
        else:
            logger.warning("⚠️ No Firecrawl events extracted")
        
        storage.close()
        return len(firecrawl_events) if firecrawl_events else 0
        
    except Exception as e:
        logger.error(f'❌ Error: {e}')
        import traceback
        logger.error(f'Full traceback: {traceback.format_exc()}')
        return 0

if __name__ == "__main__":
    result = asyncio.run(collect_firecrawl_only())
    logger.success(f'✅ Firecrawl-only test completed! Total events: {result}')