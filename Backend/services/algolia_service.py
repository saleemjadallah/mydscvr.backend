"""
Algolia Search Service - v3 API
High-performance search using Algolia
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from algoliasearch.search.client import SearchClient

logger = logging.getLogger(__name__)

class AlgoliaService:
    """Service for managing Algolia search operations"""
    
    def __init__(self):
        self.app_id = os.environ.get('ALGOLIA_APP_ID')
        self.api_key = os.environ.get('ALGOLIA_API_KEY')
        self.search_api_key = os.environ.get('ALGOLIA_SEARCH_API_KEY')
        self.index_name = os.environ.get('ALGOLIA_INDEX_NAME', 'dxb_events')
        
        self.enabled = bool(self.app_id and self.api_key)
        self.client = None
        self.index = None
        
        if self.enabled:
            try:
                self.client = SearchClient.create(self.app_id, self.api_key)
                self.index = self.client.init_index(self.index_name)
                logger.info(f"✅ Algolia initialized with index: {self.index_name}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Algolia: {e}")
                self.enabled = False
        else:
            logger.warning("⚠️ Algolia not configured - missing app_id or api_key")
    
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
    
    def _enhance_query_with_ai(self, query: str) -> str:
        """Enhance query with AI-powered synonyms and expansions"""
        # Dubai-specific location mapping
        location_synonyms = {
            'marina': 'dubai marina marina walk',
            'downtown': 'downtown dubai burj khalifa',
            'jbr': 'jumeirah beach residence the beach',
            'city walk': 'city walk al wasl',
            'mall': 'shopping mall dubai mall',
            'beach': 'beach jumeirah beach la mer',
        }
        
        # Activity synonyms for better matching
        activity_synonyms = {
            'kids': 'kids children family toddlers',
            'children': 'children kids family youth',
            'family': 'family kids children family-friendly',
            'dining': 'dining restaurant food cuisine meal',
            'entertainment': 'entertainment show performance music',
            'outdoor': 'outdoor outside beach park nature',
            'indoor': 'indoor inside mall air-conditioned',
            'free': 'free complimentary no-cost budget',
            'weekend': 'weekend saturday sunday',
        }
        
        # Time period mapping
        time_synonyms = {
            'tonight': 'today evening night',
            'tomorrow': 'tomorrow next day',
            'this weekend': 'saturday sunday weekend',
            'next weekend': 'next saturday sunday',
        }
        
        enhanced_query = query.lower()
        
        # Apply synonyms
        for term, expansion in {**location_synonyms, **activity_synonyms, **time_synonyms}.items():
            if term in enhanced_query:
                enhanced_query = enhanced_query.replace(term, expansion)
        
        return enhanced_query
    
    async def search_events(self, query: str, page: int = 1, per_page: int = 20, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Search events using Algolia v3 API with AI enhancements"""
        try:
            if not self.enabled:
                return {'error': 'Algolia not enabled'}
            
            filters = filters or {}
            
            # Enhance query with AI-powered synonyms
            enhanced_query = self._enhance_query_with_ai(query)
            
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
            
            # Advanced AI-powered search options
            search_params = {
                'page': page - 1,  # Algolia uses 0-based pagination
                'hitsPerPage': per_page,
                
                # AI-powered features
                'enableABTest': True,
                'enableRules': True,
                'enablePersonalization': False,  # Can enable if user tracking is implemented
                
                # Natural language processing
                'removeStopWords': True,
                'ignorePlurals': True,
                'removeWordsIfNoResults': 'allOptional',
                
                # Typo tolerance (AI-enhanced)
                'typoTolerance': 'true',
                'minWordSizefor1Typo': 4,
                'minWordSizefor2Typos': 8,
                
                # Query expansion and synonyms
                'synonyms': True,
                'replaceSynonymsInHighlight': True,
                
                # Advanced matching
                'optionalWords': enhanced_query,  # Treats all query words as optional for broader results
                'disableExactOnAttributes': [],
                
                # Faceting for AI understanding
                'facets': ['category', 'venue_area', 'is_free', 'family_friendly', 'is_weekend', 'weekday'],
                
                # Highlight for better UX
                'highlightPreTag': '<em>',
                'highlightPostTag': '</em>',
                'snippetEllipsisText': '…',
                
                # Analytics for AI learning
                'analytics': True,
                'analyticsTags': ['dubai-events', 'search'],
            }
            
            if filter_parts:
                search_params['filters'] = ' AND '.join(filter_parts)
            
            # Perform search with enhanced query
            index = self.client.init_index(self.index_name)
            result = await asyncio.to_thread(index.search, enhanced_query, search_params)
            
            # Transform results and ensure consistent ID fields
            events = []
            for hit in result.get('hits', []):
                event = dict(hit)
                object_id = event.get('objectID', '')
                
                # Ensure all ID fields are consistent
                event['_id'] = object_id
                event['id'] = object_id  # Frontend might expect this field
                
                # Remove Algolia-specific fields that might cause confusion
                event.pop('_highlightResult', None)
                event.pop('_snippetResult', None)
                
                events.append(event)
            
            return {
                'events': events,
                'total': result.get('nbHits', 0),
                'page': page,
                'per_page': per_page,
                'total_pages': (result.get('nbHits', 0) + per_page - 1) // per_page,
                'processing_time_ms': result.get('processingTimeMS', 0),
                'suggestions': [],
                'query_metadata': {
                    'original_query': query,
                    'enhanced_query': enhanced_query,
                    'ai_features_used': ['synonyms', 'typo_tolerance', 'query_expansion', 'nlp']
                }
            }
            
        except Exception as e:
            logger.error(f"Algolia search error: {e}")
            return {'error': str(e)}
    
    async def index_events(self, events: List[Dict[str, Any]]) -> bool:
        """Index events to Algolia"""
        if not self.enabled:
            return False
        
        try:
            algolia_docs = [self.prepare_event_for_indexing(event) for event in events]
            await asyncio.to_thread(self.index.save_objects, algolia_docs)
            logger.info(f"✅ Indexed {len(algolia_docs)} events to Algolia")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to index events: {e}")
            return False
    
    async def configure_index_settings(self) -> bool:
        """Configure Algolia index settings"""
        if not self.enabled:
            return False
        
        try:
            settings = {
                # AI-enhanced searchable attributes with priority
                'searchableAttributes': [
                    'title',
                    'description',
                    'short_description',
                    'ai_summary',
                    'category',
                    'venue.name,venue_name',
                    'venue.area,location_area,venue_area',
                    'tags',
                    'highlights',
                    'target_audience'
                ],
                
                # Advanced faceting for AI understanding
                'attributesForFaceting': [
                    'filterOnly(category)',
                    'filterOnly(venue_area)',
                    'filterOnly(is_free)',
                    'filterOnly(family_friendly)',
                    'filterOnly(is_weekend)',
                    'filterOnly(weekday)',
                    'filterOnly(age_restrictions)',
                    'filterOnly(indoor_outdoor)'
                ],
                
                # AI-powered ranking with relevance
                'customRanking': [
                    'desc(quality_score)',
                    'desc(family_score)',
                    'desc(rating)',
                    'desc(is_featured)',
                    'asc(start_date)'
                ],
                
                # NLP and AI features
                'removeStopWords': True,
                'ignorePlurals': True,
                'removeWordsIfNoResults': 'allOptional',
                'minWordSizefor1Typo': 4,
                'minWordSizefor2Typos': 8,
                'typoTolerance': True,
                'allowTyposOnNumericTokens': False,
                
                # Query expansion
                'disableExactOnAttributes': ['description', 'ai_summary'],
                'exactOnSingleWordQuery': 'attribute',
                
                # Advanced highlighting
                'highlightPreTag': '<em>',
                'highlightPostTag': '</em>',
                'snippetEllipsisText': '…',
                
                # Analytics for AI learning
                'analytics': True
            }
            
            await asyncio.to_thread(self.index.set_settings, settings)
            logger.info("✅ Algolia index settings configured")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to configure index settings: {e}")
            return False

# Global instance
algolia_service = AlgoliaService()
