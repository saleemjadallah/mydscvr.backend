"""
Algolia Search Service - v4 API
High-performance search using Algolia v4 SDK
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from algoliasearch.search.client import SearchClientSync

logger = logging.getLogger(__name__)

class AlgoliaService:
    """Service for managing Algolia search operations with v4 API"""
    
    def __init__(self):
        self.app_id = os.getenv('ALGOLIA_APP_ID')
        self.api_key = os.getenv('ALGOLIA_API_KEY')
        self.search_api_key = os.getenv('ALGOLIA_SEARCH_API_KEY')
        self.index_name = os.getenv('ALGOLIA_INDEX_NAME', 'dxb_events')
        
        self.enabled = bool(self.app_id and self.api_key)
        self.client = None
        
        if self.enabled:
            try:
                self.client = SearchClientSync(self.app_id, self.api_key)
                logger.info(f"✅ Algolia v4 initialized with index: {self.index_name}")
                logger.info(f"✅ App ID: {self.app_id}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Algolia v4: {e}")
                self.enabled = False
        else:
            logger.warning(f"⚠️ Algolia not configured - app_id: {self.app_id}, api_key: {'SET' if self.api_key else 'NOT SET'}")
    
    def prepare_event_for_indexing(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare event data for Algolia indexing"""
        # Convert ObjectId to string
        event_id = str(event.get('_id', ''))
        
        # Extract basic info
        start_date = event.get('start_date')
        weekday = None
        is_weekend = False
        
        if isinstance(start_date, datetime):
            weekday = start_date.strftime('%A').lower()
            is_weekend = weekday in ['saturday', 'sunday']
        
        # Build Algolia document - preserve all original fields
        algolia_doc = dict(event)  # Copy all fields
        
        # Add Algolia-specific fields
        algolia_doc['objectID'] = event_id
        algolia_doc['is_weekend'] = is_weekend
        algolia_doc['weekday'] = weekday
        
        # Ensure consistent naming
        algolia_doc['family_friendly'] = event.get('family_friendly', False) or event.get('is_family_friendly', False)
        algolia_doc['venue_area'] = event.get('venue_area', event.get('location_area', ''))
        
        # Convert dates to ISO strings
        if isinstance(algolia_doc.get('start_date'), datetime):
            algolia_doc['start_date'] = algolia_doc['start_date'].isoformat()
        if isinstance(algolia_doc.get('end_date'), datetime):
            algolia_doc['end_date'] = algolia_doc['end_date'].isoformat()
        
        # Remove MongoDB _id
        algolia_doc.pop('_id', None)
        
        return algolia_doc
    
    async def search_events(self, query: str, page: int = 1, per_page: int = 20, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Search events using Algolia v4 API"""
        try:
            if not self.enabled:
                return {'error': 'Algolia not enabled'}
            
            filters = filters or {}
            
            # Build filters
            filter_parts = []
            if filters.get('category'):
                filter_parts.append(f"category:{filters['category']}")
            if filters.get('area'):
                filter_parts.append(f"venue_area:{filters['area']}")
            if filters.get('is_free'):
                filter_parts.append("is_free:true")
            if filters.get('family_friendly'):
                filter_parts.append("family_friendly:true")
            if filters.get('is_weekend') or filters.get('this_weekend'):
                filter_parts.append("is_weekend:true")
            
            # Search parameters for v4 API
            search_params = {
                'page': page - 1,  # Algolia uses 0-based pagination
                'hitsPerPage': per_page,
            }
            if filter_parts:
                search_params['filters'] = ' AND '.join(filter_parts)
            
            # Perform search using v4 API
            result = await asyncio.to_thread(
                self.client.search_single_index, 
                self.index_name, 
                query, 
                search_params
            )
            
            # Transform results
            events = []
            for hit in result.get('hits', []):
                event = dict(hit)
                event['_id'] = event.get('objectID', '')
                events.append(event)
            
            return {
                'events': events,
                'total': result.get('nbHits', 0),
                'page': page,
                'per_page': per_page,
                'total_pages': (result.get('nbHits', 0) + per_page - 1) // per_page,
                'processing_time_ms': result.get('processingTimeMS', 0),
                'suggestions': [],
            }
            
        except Exception as e:
            logger.error(f"Algolia search error: {e}")
            return {'error': str(e)}
    
    async def index_events(self, events: List[Dict[str, Any]]) -> bool:
        """Index events to Algolia using v4 API"""
        if not self.enabled:
            return False
        
        try:
            algolia_docs = [self.prepare_event_for_indexing(event) for event in events]
            await asyncio.to_thread(self.client.save_objects, self.index_name, algolia_docs)
            logger.info(f"✅ Indexed {len(algolia_docs)} events to Algolia")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to index events: {e}")
            return False
    
    async def configure_index_settings(self) -> bool:
        """Configure Algolia index settings using v4 API"""
        if not self.enabled:
            return False
        
        try:
            settings = {
                'searchableAttributes': [
                    'title',
                    'description',
                    'location_name',
                    'venue_name',
                    'location_area',
                    'tags',
                    'category'
                ],
                'attributesForFaceting': [
                    'filterOnly(category)',
                    'filterOnly(venue_area)', 
                    'filterOnly(is_free)',
                    'filterOnly(family_friendly)',
                    'filterOnly(is_weekend)',
                    'filterOnly(weekday)'
                ],
                'customRanking': [
                    'desc(relevance_score)',
                    'desc(start_date)'
                ]
            }
            
            await asyncio.to_thread(self.client.set_settings, self.index_name, settings)
            logger.info("✅ Algolia index settings configured")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to configure index settings: {e}")
            return False

# Global instance
algolia_service = AlgoliaService()