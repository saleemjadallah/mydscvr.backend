"""
Algolia Search Service
High-performance search using Algolia's powerful indexing
"""

import os
import logging
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
                self.client = SearchClient(self.app_id, self.api_key)
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
        start_date_str = None
        end_date_str = None
        
        if start_date:
            if isinstance(start_date, str):
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    start_timestamp = int(start_dt.timestamp())
                    weekday = start_dt.weekday()  # 0=Monday, 6=Sunday
                    start_date_str = start_date
                except:
                    start_date_str = start_date
            elif isinstance(start_date, datetime):
                start_timestamp = int(start_date.timestamp())
                weekday = start_date.weekday()
                start_date_str = start_date.isoformat()
        
        if end_date:
            if isinstance(end_date, str):
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    end_timestamp = int(end_dt.timestamp())
                    end_date_str = end_date
                except:
                    end_date_str = end_date
            elif isinstance(end_date, datetime):
                end_timestamp = int(end_date.timestamp())
                end_date_str = end_date.isoformat()
        
        # Enhanced family-friendly detection
        family_friendly = (
            event.get('is_family_friendly', False) or
            event.get('family_score', 0) >= 70 or
            any(tag in str(event.get('tags', [])).lower() for tag in ['family', 'kids', 'children', 'child']) or
            event.get('category') in ['family_activities', 'educational', 'kids_activities'] or
            any(keyword in str(event.get('title', '')).lower() for keyword in ['kids', 'children', 'family', 'child']) or
            any(keyword in str(event.get('description', '')).lower() for keyword in ['kids', 'children', 'family', 'child'])
        )
        
        # Create enhanced searchable text fields with keywords
        searchable_keywords = []
        
        # Add family/kids keywords if applicable
        if family_friendly:
            searchable_keywords.extend(['family-friendly', 'kids', 'children', 'family'])
        
        # Add weekend keywords if applicable  
        if weekday in [5, 6]:
            searchable_keywords.extend(['weekend', 'saturday' if weekday == 5 else 'sunday'])
        
        # Add free keywords if applicable
        if is_free:
            searchable_keywords.extend(['free', 'no-cost', 'complimentary'])
            
        searchable_text = ' '.join(filter(None, [
            event.get('title', ''),
            event.get('description', ''),
            venue_name,
            venue_area,
            event.get('category', ''),
            ' '.join(event.get('tags', [])),
            ' '.join(searchable_keywords)
        ])).strip()
        
        # START WITH COMPLETE ORIGINAL EVENT DATA - preserve everything!
        algolia_doc = {}
        
        # Copy all original fields with proper serialization
        for key, value in event.items():
            if isinstance(value, datetime):
                # Convert datetime to ISO string
                algolia_doc[key] = value.isoformat()
            elif hasattr(value, 'to_dict'):
                # Handle objects with to_dict method
                algolia_doc[key] = value.to_dict()
            elif key == '_id':
                # Convert MongoDB ObjectId to string
                algolia_doc[key] = str(value)
            else:
                # Copy other values as-is
                algolia_doc[key] = value
        
        # Update the ObjectID for Algolia
        algolia_doc['objectID'] = event_id
        
        # Ensure consistent field naming with regular events API
        algolia_doc['id'] = event_id
        algolia_doc['is_family_friendly'] = family_friendly  # Use consistent naming
        algolia_doc['family_friendly'] = family_friendly    # Keep both for backward compatibility
        
        # Enhanced venue information (preserve original + add search-friendly fields)
        algolia_doc.update({
            'venue_name': venue_name,
            'venue_area': venue_area,
            'venue_city': venue_city,
            'location': f"{venue_area}, {venue_city}".strip(', '),
        })
        
        # Enhanced date and time information for search filtering
        algolia_doc.update({
            'start_date': start_date_str,  # Override with properly formatted string
            'end_date': end_date_str,     # Override with properly formatted string
            'start_timestamp': start_timestamp,
            'end_timestamp': end_timestamp,
            'weekday': weekday,  # 0-6, where 5=Saturday, 6=Sunday
            'is_weekend': weekday in [5, 6] if weekday is not None else False,
        })
        
        # Enhanced price information for filtering
        algolia_doc.update({
            'base_price': float(base_price) if base_price else 0,
            'is_free': is_free,
            'price_tier': 'free' if is_free else ('budget' if base_price < 100 else ('mid' if base_price < 300 else 'premium')),
        })
        
        # Enhanced searchability and ranking (add to existing data)
        algolia_doc.update({
            # Searchable content (for full-text search)
            '_searchable_text': searchable_text,
            
            # Ranking factors for Algolia
            'popularity_score': 0,  # Can be updated based on clicks/views
            'quality_score': event.get('quality_metrics', {}).get('data_completeness', 0.5) if event.get('quality_metrics') else 0.5,
            
            # Current timestamp for freshness ranking
            'indexed_at': int(datetime.now().timestamp())
        })
        
        # Ensure ObjectId is converted to string if it's a MongoDB ObjectId
        if '_id' in algolia_doc:
            algolia_doc['_id'] = str(algolia_doc['_id'])
            
        # Remove any fields that shouldn't be indexed (like internal MongoDB fields)
        algolia_doc.pop('_id', None)  # Remove MongoDB _id, we use objectID instead
        
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
            
            # Batch index to Algolia using v4 API
            if algolia_docs:
                response = await self.client.save_objects(
                    index_name=self.index_name,
                    objects=algolia_docs
                )
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
                'attributesToRetrieve': ['*'],  # Retrieve ALL fields for consistency
                'attributesToHighlight': ['title', 'description', 'venue_name'],
                'facets': [
                    'category',
                    'venue_area',
                    'is_free',
                    'family_friendly',
                    'price_tier',
                    'is_weekend',
                    'weekday'
                ],
                'maxValuesPerFacet': 20,
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
            
            # Perform search using v4 API
            search_request = {
                "indexName": self.index_name,
                "query": query,
                **search_params
            }
            
            response = await self.client.search(
                search_method_params={
                    "requests": [search_request]
                }
            )
            
            # Process results - v4 API returns results in different structure
            events = []
            
            # Handle different response structures
            if hasattr(response, 'results') and response.results:
                search_results = response.results[0]
                
                # Check if we need to unwrap the actual instance
                if hasattr(search_results, 'actual_instance'):
                    search_results = search_results.actual_instance
            else:
                search_results = response
            
            # Extract hits
            if hasattr(search_results, 'hits'):
                hits = search_results.hits
            elif isinstance(search_results, dict) and 'hits' in search_results:
                hits = search_results['hits']
            else:
                hits = []
            
            for hit in hits:
                # Handle hit data extraction - check if it's a Pydantic model or dict
                if hasattr(hit, 'model_dump'):
                    hit_dict = hit.model_dump()
                elif hasattr(hit, '__dict__'):
                    hit_dict = hit.__dict__
                else:
                    hit_dict = hit if isinstance(hit, dict) else {}
                
                # USE COMPLETE EVENT DATA - preserve all fields for consistency!
                event = dict(hit_dict)  # Start with all available data
                
                # Ensure consistent field naming and required fields
                event['id'] = hit_dict.get('objectID', hit_dict.get('object_id', hit_dict.get('id', '')))
                event['is_saved'] = False  # Always false for search results
                
                # Ensure venue structure is consistent (preserve existing if it exists)
                if 'venue' not in event or not isinstance(event['venue'], dict):
                    event['venue'] = {
                        'name': hit_dict.get('venue_name', ''),
                        'area': hit_dict.get('venue_area', ''),
                        'city': hit_dict.get('venue_city', 'Dubai')
                    }
                
                # Ensure price structure is consistent (preserve existing if it exists)
                if 'price' not in event or not isinstance(event['price'], dict):
                    event['price'] = {
                        'base_price': hit_dict.get('base_price', 0),
                        'currency': 'AED',
                        'is_free': hit_dict.get('is_free', False)
                    }
                events.append(event)
            
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            total_hits = getattr(search_results, 'nb_hits', getattr(search_results, 'nbHits', 0))
            
            # Extract facets from search results
            facets = {}
            if hasattr(search_results, 'facets'):
                facets = search_results.facets or {}
            elif hasattr(search_results, '__dict__') and 'facets' in search_results.__dict__:
                facets = search_results.__dict__['facets'] or {}
            
            return {
                "events": events,
                "total": total_hits,
                "page": page,
                "per_page": per_page,
                "total_pages": (total_hits + per_page - 1) // per_page,
                "has_next": page * per_page < total_hits,
                "has_prev": page > 1,
                "suggestions": self._generate_suggestions(query, search_results),
                "facets": facets,
                "processing_time_ms": processing_time,
                "search_metadata": {
                    "query": query,
                    "filters_applied": filter_string,
                    "algolia_query_time": getattr(search_results, 'processing_time_ms', getattr(search_results, 'processingTimeMS', 0))
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
                'replicas': [
                    f'{self.index_name}_price_asc',
                    f'{self.index_name}_date_asc'
                ],
                'attributesToSnippet': [
                    'description:20'
                ],
                'snippetEllipsisText': '…',
                'highlightPreTag': '<em>',
                'highlightPostTag': '</em>',
                'synonyms': [
                    ['kids', 'children', 'child'],
                    ['family', 'family-friendly', 'family friendly'],
                    ['weekend', 'saturday', 'sunday'],
                    ['this week', 'weekly', 'week'],
                    ['free', 'no cost', 'complimentary'],
                    ['activities', 'events', 'experiences'],
                    ['dubai', 'uae', 'emirates']
                ],
                'typoTolerance': 'true',
                'minWordSizefor1Typo': 4,
                'minWordSizefor2Typos': 8
            }
            
            await self.client.set_settings(
                index_name=self.index_name,
                index_settings=settings
            )
            logger.info("✅ Algolia index settings configured")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to configure Algolia settings: {e}")
            return False

# Global instance
algolia_service = AlgoliaService()