"""
Algolia Search Service
High-performance search using Algolia's powerful indexing
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from algoliasearch.search.client import SearchClient
from algoliasearch.search.models.search_for_hits import SearchForHits

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
        """
        Prepare event data for Algolia indexing with optimized searchable attributes
        """
        # Convert ObjectId to string
        event_id = str(event.get('_id', ''))
        
        # Extract venue information
        venue = event.get('venue', {})
        venue_name = venue.get('name', '') if venue else ''
        venue_area = venue.get('area', '') if venue else ''
        venue_city = venue.get('city', 'Dubai') if venue else 'Dubai'
        
        # Extract pricing information
        price_info = event.get('price', {}) or event.get('pricing', {})
        base_price = price_info.get('base_price', 0) if price_info else 0
        is_free = price_info.get('is_free', base_price == 0) if price_info else (base_price == 0)
        
        # Prepare dates for filtering
        start_date = event.get('start_date')
        end_date = event.get('end_date')
        
        # Convert to timestamps for Algolia filtering
        start_timestamp = None
        end_timestamp = None
        weekday = None
        
        if start_date:
            if isinstance(start_date, str):
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    start_timestamp = int(start_dt.timestamp())
                    weekday = start_dt.weekday()  # 0=Monday, 6=Sunday
                except:
                    pass
            elif isinstance(start_date, datetime):
                start_timestamp = int(start_date.timestamp())
                weekday = start_date.weekday()
        
        if end_date:
            if isinstance(end_date, str):
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    end_timestamp = int(end_dt.timestamp())
                except:
                    pass
            elif isinstance(end_date, datetime):
                end_timestamp = int(end_date.timestamp())
        
        # Determine if it's family-friendly
        family_friendly = (
            event.get('is_family_friendly', False) or
            event.get('family_score', 0) >= 70 or
            any(tag in str(event.get('tags', [])).lower() for tag in ['family', 'kids', 'children']) or
            event.get('category') in ['family_activities', 'educational']
        )
        
        # Create searchable text fields
        searchable_text = ' '.join(filter(None, [
            event.get('title', ''),
            event.get('description', ''),
            venue_name,
            venue_area,
            event.get('category', ''),
            ' '.join(event.get('tags', [])),
        ])).strip()
        
        # Prepare the document for Algolia
        algolia_doc = {
            'objectID': event_id,
            'title': event.get('title', ''),
            'description': event.get('description', ''),
            'category': event.get('category', ''),
            'primary_category': event.get('primary_category', event.get('category', '')),
            'tags': event.get('tags', []),
            
            # Venue information
            'venue_name': venue_name,
            'venue_area': venue_area,
            'venue_city': venue_city,
            'location': f"{venue_area}, {venue_city}".strip(', '),
            
            # Date and time information
            'start_date': event.get('start_date'),
            'end_date': event.get('end_date'),
            'start_timestamp': start_timestamp,
            'end_timestamp': end_timestamp,
            'weekday': weekday,  # 0-6, where 5=Saturday, 6=Sunday
            'is_weekend': weekday in [5, 6] if weekday is not None else False,
            
            # Price information
            'base_price': float(base_price) if base_price else 0,
            'is_free': is_free,
            'price_tier': 'free' if is_free else ('budget' if base_price < 100 else ('mid' if base_price < 300 else 'premium')),
            
            # Family and age information
            'family_friendly': family_friendly,
            'family_score': event.get('family_score', 0),
            'age_range': event.get('age_range', 'All ages'),
            
            # Additional metadata
            'source_name': event.get('source_name', ''),
            'image_urls': event.get('image_urls', []),
            'booking_url': event.get('booking_url'),
            
            # Searchable content (for full-text search)
            '_searchable_text': searchable_text,
            
            # Ranking factors
            'popularity_score': 0,  # Can be updated based on clicks/views
            'quality_score': event.get('quality_metrics', {}).get('data_completeness', 0.5) if event.get('quality_metrics') else 0.5,
            
            # Current timestamp for freshness ranking
            'indexed_at': int(datetime.now().timestamp())
        }
        
        return algolia_doc
    
    async def index_events(self, events: List[Dict[str, Any]]) -> bool:
        """
        Index a batch of events to Algolia
        """
        if not self.enabled:
            logger.warning("Algolia not enabled, skipping indexing")
            return False
        
        try:
            # Prepare events for indexing
            algolia_docs = []
            for event in events:
                doc = self.prepare_event_for_indexing(event)
                algolia_docs.append(doc)
            
            # Batch index to Algolia
            if algolia_docs:
                response = self.index.save_objects(algolia_docs)
                logger.info(f"✅ Indexed {len(algolia_docs)} events to Algolia")
                return True
            
        except Exception as e:
            logger.error(f"❌ Failed to index events to Algolia: {e}")
            return False
        
        return False
    
    async def search_events(
        self,
        query: str,
        page: int = 1,
        per_page: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search events using Algolia with advanced filtering
        """
        if not self.enabled:
            logger.warning("Algolia not enabled")
            return {
                "events": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0,
                "suggestions": [],
                "processing_time_ms": 0
            }
        
        try:
            start_time = datetime.now()
            
            # Build Algolia filter string
            filter_parts = []
            
            if filters:
                # Date filtering
                if filters.get('date_from'):
                    timestamp = int(filters['date_from'].timestamp())
                    filter_parts.append(f"start_timestamp >= {timestamp}")
                
                if filters.get('date_to'):
                    timestamp = int(filters['date_to'].timestamp())
                    filter_parts.append(f"start_timestamp <= {timestamp}")
                
                # This weekend filter
                if filters.get('this_weekend'):
                    filter_parts.append("is_weekend:true")
                
                # Category filtering
                if filters.get('category'):
                    categories = filters['category'] if isinstance(filters['category'], list) else [filters['category']]
                    category_filters = ' OR '.join([f'category:"{cat}"' for cat in categories])
                    filter_parts.append(f"({category_filters})")
                
                # Family-friendly filtering
                if filters.get('family_friendly'):
                    filter_parts.append("family_friendly:true")
                
                # Price filtering
                if filters.get('price_max'):
                    filter_parts.append(f"base_price <= {filters['price_max']}")
                
                if filters.get('price_min'):
                    filter_parts.append(f"base_price >= {filters['price_min']}")
                
                if filters.get('is_free'):
                    filter_parts.append("is_free:true")
                
                # Location filtering
                if filters.get('area'):
                    filter_parts.append(f'venue_area:"{filters["area"]}"')
            
            # Combine filters
            filter_string = ' AND '.join(filter_parts) if filter_parts else ''
            
            # Search parameters
            search_params = {
                'hitsPerPage': per_page,
                'page': page - 1,  # Algolia uses 0-based pagination
                'attributesToRetrieve': [
                    'objectID', 'title', 'description', 'category', 'start_date', 'end_date',
                    'venue_name', 'venue_area', 'venue_city', 'base_price', 'is_free',
                    'family_friendly', 'age_range', 'tags', 'image_urls', 'booking_url'
                ],
                'attributesToHighlight': ['title', 'description', 'venue_name'],
                'ranking': [
                    'typo',
                    'geo',
                    'words',
                    'filters',
                    'proximity',
                    'attribute',
                    'exact',
                    'custom'
                ]
            }
            
            if filter_string:
                search_params['filters'] = filter_string
            
            # Perform search
            response = self.index.search(SearchForHits(query=query, **search_params))
            
            # Process results
            events = []
            for hit in response['hits']:
                event = {
                    'id': hit['objectID'],
                    'title': hit.get('title', ''),
                    'description': hit.get('description', ''),
                    'category': hit.get('category', ''),
                    'start_date': hit.get('start_date'),
                    'end_date': hit.get('end_date'),
                    'venue': {
                        'name': hit.get('venue_name', ''),
                        'area': hit.get('venue_area', ''),
                        'city': hit.get('venue_city', 'Dubai')
                    },
                    'price': {
                        'base_price': hit.get('base_price', 0),
                        'currency': 'AED',
                        'is_free': hit.get('is_free', False)
                    },
                    'family_friendly': hit.get('family_friendly', False),
                    'age_range': hit.get('age_range', 'All ages'),
                    'tags': hit.get('tags', []),
                    'image_urls': hit.get('image_urls', []),
                    'booking_url': hit.get('booking_url'),
                    'is_saved': False,
                    'source_name': 'algolia',
                    # Add highlighting if available
                    '_highlightResult': hit.get('_highlightResult', {})
                }
                events.append(event)
            
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return {
                "events": events,
                "total": response['nbHits'],
                "page": page,
                "per_page": per_page,
                "total_pages": (response['nbHits'] + per_page - 1) // per_page,
                "suggestions": self._generate_suggestions(query, response),
                "processing_time_ms": processing_time,
                "search_metadata": {
                    "query": query,
                    "filters_applied": filter_string,
                    "algolia_query_time": response.get('processingTimeMS', 0)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Algolia search failed: {e}")
            return {
                "events": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0,
                "suggestions": [],
                "processing_time_ms": 0,
                "error": str(e)
            }
    
    def _generate_suggestions(self, query: str, response: Dict) -> List[str]:
        """
        Generate search suggestions based on query and results
        """
        suggestions = []
        
        # Add category-based suggestions
        if 'kids' in query.lower():
            suggestions.extend([
                "family activities in Dubai",
                "children's workshops",
                "kids entertainment",
                "educational events for kids"
            ])
        elif 'weekend' in query.lower():
            suggestions.extend([
                "weekend events in Dubai",
                "Saturday activities",
                "Sunday events",
                "weekend family fun"
            ])
        elif 'free' in query.lower():
            suggestions.extend([
                "free events in Dubai", 
                "budget-friendly activities",
                "no-cost entertainment",
                "complimentary events"
            ])
        else:
            suggestions.extend([
                "events this weekend",
                "family activities",
                "free events",
                "indoor activities"
            ])
        
        return suggestions[:4]  # Limit to 4 suggestions
    
    async def configure_index_settings(self):
        """
        Configure Algolia index settings for optimal search performance
        """
        if not self.enabled:
            return False
        
        try:
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
                    'category',
                    'venue_area',
                    'is_free',
                    'family_friendly',
                    'price_tier',
                    'is_weekend'
                ],
                'customRanking': [
                    'desc(popularity_score)',
                    'desc(quality_score)',
                    'asc(start_timestamp)'
                ],
                'replicas': [
                    f'{self.index_name}_price_asc',
                    f'{self.index_name}_date_asc'
                ],
                'attributesToSnippet': [
                    'description:20'
                ],
                'snippetEllipsisText': '…',
                'highlightPreTag': '<em>',
                'highlightPostTag': '</em>'
            }
            
            self.index.set_settings(settings)
            logger.info("✅ Algolia index settings configured")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to configure Algolia settings: {e}")
            return False

# Global instance
algolia_service = AlgoliaService()