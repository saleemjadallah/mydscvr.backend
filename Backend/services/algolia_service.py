"""
Algolia Search Service - v3 API
High-performance search using Algolia
"""

import os
import logging
import asyncio
import time
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
    
    def extract_intent(self, query: str) -> dict:
        """Extract user intent from query using AI understanding"""
        intent_patterns = {
            'family': ['kids', 'children', 'family', 'toddler', 'baby', 'child'],
            'nightlife': ['bar', 'club', 'night', 'party', 'cocktail', 'drinks'],
            'cultural': ['art', 'museum', 'gallery', 'culture', 'exhibition', 'heritage'],
            'outdoor': ['park', 'beach', 'outdoor', 'nature', 'hiking', 'cycling'],
            'food': ['restaurant', 'food', 'dining', 'brunch', 'lunch', 'dinner', 'cuisine'],
            'entertainment': ['show', 'concert', 'music', 'performance', 'comedy', 'theater'],
            'shopping': ['mall', 'shopping', 'market', 'boutique', 'store'],
            'fitness': ['gym', 'fitness', 'workout', 'sports', 'yoga', 'pilates'],
            'educational': ['workshop', 'class', 'learning', 'seminar', 'course'],
            'luxury': ['luxury', 'premium', 'vip', 'exclusive', 'upscale']
        }
        
        detected_intents = []
        confidence_scores = {}
        
        query_lower = query.lower()
        for intent, keywords in intent_patterns.items():
            matches = sum(1 for keyword in keywords if keyword in query_lower)
            if matches > 0:
                detected_intents.append(intent)
                confidence_scores[intent] = matches / len(keywords)
        
        return {
            'detected_intents': detected_intents,
            'confidence_scores': confidence_scores,
            'primary_intent': max(confidence_scores.keys(), key=confidence_scores.get) if confidence_scores else None
        }
    
    def _enhance_query_with_ai(self, query: str) -> str:
        """Enhanced AI-powered query expansion with intent understanding"""
        # Extract intent first
        intent_data = self.extract_intent(query)
        
        # Dubai-specific location mapping with semantic understanding
        location_synonyms = {
            'marina': 'dubai marina marina walk waterfront',
            'downtown': 'downtown dubai burj khalifa business district',
            'jbr': 'jumeirah beach residence the beach walk',
            'city walk': 'city walk al wasl district',
            'mall': 'shopping mall dubai mall emirates mall',
            'beach': 'beach jumeirah beach la mer kite beach',
            'old dubai': 'old dubai al fahidi bastakiya creek',
            'palm': 'palm jumeirah atlantis',
            'business bay': 'business bay canal district towers'
        }
        
        # Intent-based activity synonyms
        activity_synonyms = {
            'kids': 'kids children family toddlers youth activities',
            'children': 'children kids family youth toddlers',
            'family': 'family kids children family-friendly suitable',
            'dining': 'dining restaurant food cuisine meal brunch',
            'entertainment': 'entertainment show performance music concert',
            'outdoor': 'outdoor outside beach park nature activities',
            'indoor': 'indoor inside mall air-conditioned venue',
            'free': 'free complimentary no-cost budget affordable',
            'weekend': 'weekend saturday sunday',
            'luxury': 'luxury premium vip exclusive upscale high-end',
            'fitness': 'fitness gym workout sports active health',
            'cultural': 'cultural art museum heritage traditional'
        }
        
        # Time-aware enhancements
        time_synonyms = {
            'tonight': 'today evening night after work',
            'tomorrow': 'tomorrow next day',
            'this weekend': 'saturday sunday weekend',
            'next weekend': 'next saturday sunday upcoming weekend',
            'today': 'today now current'
        }
        
        enhanced_query = query.lower()
        
        # Apply intent-based enhancements
        if intent_data['primary_intent']:
            primary_intent = intent_data['primary_intent']
            if primary_intent == 'family' and 'weekend' in enhanced_query:
                enhanced_query += ' family-friendly children activities'
            elif primary_intent == 'food' and any(area in enhanced_query for area in ['marina', 'downtown', 'jbr']):
                enhanced_query += ' restaurant dining experience'
            elif primary_intent == 'outdoor' and 'free' in enhanced_query:
                enhanced_query += ' park beach outdoor activities'
        
        # Apply all synonym expansions
        for term, expansion in {**location_synonyms, **activity_synonyms, **time_synonyms}.items():
            if term in enhanced_query:
                enhanced_query = enhanced_query.replace(term, expansion)
        
        # Limit length to prevent API errors
        return enhanced_query[:400]
    
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
            
            # Intent-based query enhancement
            intent_data = self.extract_intent(query)
            
            # Advanced AI-powered search options with NeuralSearch simulation
            search_params = {
                'page': page - 1,  # Algolia uses 0-based pagination
                'hitsPerPage': per_page,
                
                # AI-powered features (v3 compatible)
                'enableABTest': True,
                'enableRules': True,
                'enablePersonalization': False,  # Enable with user tracking
                
                # Natural language processing
                'removeStopWords': True,
                'ignorePlurals': True,
                'removeWordsIfNoResults': 'allOptional',
                'queryType': 'prefixAll',  # Better for partial matches
                
                # Advanced typo tolerance
                'typoTolerance': 'true',
                'minWordSizefor1Typo': 3,  # More lenient for better UX
                'minWordSizefor2Typos': 7,
                'allowTyposOnNumericTokens': False,
                
                # Query expansion and synonyms
                'synonyms': True,
                'replaceSynonymsInHighlight': True,
                'optionalWords': enhanced_query,
                
                # Advanced matching with AI simulation
                'disableExactOnAttributes': ['description', 'short_description'],
                'exactOnSingleWordQuery': 'attribute',
                'alternativesAsExact': ['ignorePlurals', 'singleWordSynonym'],
                
                # Intent-based faceting
                'facets': self._get_intent_based_facets(intent_data),
                
                # Enhanced highlighting
                'highlightPreTag': '<mark class="algolia-highlight">',
                'highlightPostTag': '</mark>',
                'snippetEllipsisText': '…',
                'restrictHighlightAndSnippetArrays': True,
                
                # Analytics for AI learning
                'analytics': True,
                'analyticsTags': ['dubai-events', 'ai-search', f"intent-{intent_data.get('primary_intent', 'general')}"],
                'clickAnalytics': True,
                'getRankingInfo': True,  # For AI optimization
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
            
            # Generate AI-powered suggestions
            suggestions = self._generate_ai_suggestions(query, intent_data, result.get('nbHits', 0))
            
            return {
                'events': events,
                'total': result.get('nbHits', 0),
                'page': page,
                'per_page': per_page,
                'total_pages': (result.get('nbHits', 0) + per_page - 1) // per_page,
                'processing_time_ms': result.get('processingTimeMS', 0),
                'suggestions': suggestions,
                'query_metadata': {
                    'original_query': query,
                    'enhanced_query': enhanced_query,
                    'intent_analysis': intent_data,
                    'ai_features_used': ['intent_detection', 'semantic_expansion', 'typo_tolerance', 'dynamic_ranking'],
                    'search_strategy': 'hybrid_ai_enhanced'
                }
            }
            
        except Exception as e:
            logger.error(f"Algolia search error: {e}")
            return {'error': str(e)}
    
    def _get_intent_based_facets(self, intent_data: dict) -> List[str]:
        """Get facets based on detected intent for better filtering"""
        base_facets = ['category', 'venue_area', 'is_free', 'family_friendly', 'is_weekend', 'weekday']
        
        if intent_data.get('primary_intent'):
            intent = intent_data['primary_intent']
            if intent == 'family':
                base_facets.extend(['age_restrictions', 'indoor_outdoor'])
            elif intent == 'food':
                base_facets.extend(['price_tier', 'cuisine_type'])
            elif intent == 'nightlife':
                base_facets.extend(['age_restrictions', 'dress_code'])
            elif intent == 'outdoor':
                base_facets.extend(['weather_dependent', 'indoor_outdoor'])
        
        return list(set(base_facets))  # Remove duplicates
    
    def _generate_ai_suggestions(self, query: str, intent_data: dict, results_count: int) -> List[str]:
        """Generate intelligent search suggestions based on AI analysis"""
        suggestions = []
        
        # If no results, suggest broader terms
        if results_count == 0:
            if intent_data.get('primary_intent'):
                intent = intent_data['primary_intent']
                suggestions.extend([
                    f"{intent} activities dubai",
                    f"{intent} events this weekend",
                    f"free {intent} events"
                ])
            else:
                suggestions.extend([
                    "family activities dubai",
                    "weekend events dubai",
                    "free events dubai"
                ])
        
        # Location-based suggestions
        dubai_areas = ['marina', 'downtown', 'jbr', 'business bay', 'jumeirah']
        for area in dubai_areas:
            if area not in query.lower():
                suggestions.append(f"{query} in {area}")
                if len(suggestions) >= 5:
                    break
        
        # Time-based suggestions
        if 'weekend' not in query.lower():
            suggestions.append(f"{query} this weekend")
        if 'free' not in query.lower():
            suggestions.append(f"free {query}")
        
        return suggestions[:5]  # Limit to 5 suggestions
    
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
                # AI-enhanced searchable attributes with semantic priority
                'searchableAttributes': [
                    'title',                    # Highest priority
                    'description',              # Core content
                    'unordered(short_description)', # Summary content
                    'unordered(ai_summary)',    # AI-generated insights
                    'unordered(category)',      # Event classification
                    'unordered(venue.name,venue_name)', # Venue information
                    'unordered(venue.area,location_area,venue_area)', # Location data
                    'unordered(tags)',          # Metadata tags
                    'unordered(highlights)',    # Key features
                    'unordered(target_audience)', # Audience targeting
                    'unordered(semantic_keywords)', # AI-extracted keywords
                    'unordered(accessibility_features)' # Accessibility info
                ],
                
                # Advanced faceting for AI understanding and personalization
                'attributesForFaceting': [
                    'filterOnly(category)',
                    'filterOnly(venue_area)',
                    'filterOnly(is_free)',
                    'filterOnly(family_friendly)',
                    'filterOnly(is_weekend)',
                    'filterOnly(weekday)',
                    'filterOnly(age_restrictions)',
                    'filterOnly(indoor_outdoor)',
                    'filterOnly(price_tier)',
                    'filterOnly(accessibility_level)',
                    'filterOnly(duration_category)',
                    'filterOnly(weather_dependent)',
                    'searchable(venue_name)',
                    'searchable(location_area)'
                ],
                
                # AI-enhanced custom ranking for optimal relevance
                'customRanking': [
                    'desc(ai_relevance_score)',   # AI-computed relevance
                    'desc(popularity_score)',     # User behavior-based
                    'desc(quality_score)',        # Content quality
                    'desc(engagement_score)',     # User engagement
                    'desc(is_featured)',          # Editorial priority
                    'desc(rating)',               # User ratings
                    'asc(start_date)'            # Temporal relevance
                ],
                
                # Advanced NLP and AI features
                'removeStopWords': ['en'],      # Multi-language support
                'ignorePlurals': ['en'],        # English plurals
                'removeWordsIfNoResults': 'allOptional',
                'minWordSizefor1Typo': 3,       # More lenient for UX
                'minWordSizefor2Typos': 7,
                'typoTolerance': True,
                'allowTyposOnNumericTokens': False,
                
                # AI-powered query expansion
                'disableExactOnAttributes': ['description', 'ai_summary', 'highlights'],
                'exactOnSingleWordQuery': 'attribute',
                'alternativesAsExact': ['ignorePlurals', 'singleWordSynonym'],
                'queryType': 'prefixAll',       # Better partial matching
                
                # Enhanced highlighting for AI results
                'highlightPreTag': '<mark class="ai-highlight">',
                'highlightPostTag': '</mark>',
                'snippetEllipsisText': '…',
                'restrictHighlightAndSnippetArrays': True,
                
                # Analytics and AI learning
                'analytics': True,
                'clickAnalytics': True,         # Track user interactions
                'enableRules': True,            # Allow dynamic rules
                'enableABTest': True           # A/B testing capability
            }
            
            await asyncio.to_thread(self.index.set_settings, settings)
            logger.info("✅ Algolia index settings configured")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to configure index settings: {e}")
            return False
    
    async def track_search_event(self, query: str, user_id: str, results_count: int) -> bool:
        """Track search events for AI learning and analytics"""
        if not self.enabled:
            return False
        
        try:
            # For now, log the event - can be extended to send to Algolia Insights API
            logger.info(f"Search Event: user={user_id}, query='{query}', results={results_count}")
            return True
        except Exception as e:
            logger.error(f"Failed to track search event: {e}")
            return False
    
    async def track_click_event(self, query: str, user_id: str, object_id: str, position: int) -> bool:
        """Track click events for AI learning and ranking optimization"""
        if not self.enabled:
            return False
        
        try:
            # For now, log the event - can be extended to send to Algolia Insights API
            logger.info(f"Click Event: user={user_id}, query='{query}', object={object_id}, position={position}")
            return True
        except Exception as e:
            logger.error(f"Failed to track click event: {e}")
            return False
    
    async def get_search_analytics(self) -> Dict[str, Any]:
        """Get search analytics for AI insights"""
        if not self.enabled:
            return {'error': 'Algolia not enabled'}
        
        try:
            # For v3 API, we can implement basic analytics
            # In production, this would integrate with Algolia Analytics API
            return {
                'status': 'analytics_available',
                'features': [
                    'search_tracking',
                    'click_tracking',
                    'conversion_tracking',
                    'ai_insights'
                ],
                'message': 'Analytics tracking is active for AI optimization'
            }
        except Exception as e:
            logger.error(f"Failed to get analytics: {e}")
            return {'error': str(e)}
    
    def generate_semantic_keywords(self, event: Dict[str, Any]) -> List[str]:
        """Generate semantic keywords for better AI search matching"""
        keywords = []
        
        # Extract from title and description
        title = event.get('title', '').lower()
        description = event.get('description', '').lower()
        category = event.get('category', '').lower()
        
        # Intent-based keyword generation
        if any(word in f"{title} {description}" for word in ['kid', 'child', 'family']):
            keywords.extend(['family-friendly', 'children-activities', 'kid-suitable'])
        
        if any(word in f"{title} {description}" for word in ['food', 'dining', 'restaurant']):
            keywords.extend(['culinary', 'gastronomy', 'dining-experience'])
        
        if any(word in f"{title} {description}" for word in ['art', 'culture', 'museum']):
            keywords.extend(['cultural', 'artistic', 'heritage', 'creative'])
        
        if any(word in f"{title} {description}" for word in ['outdoor', 'beach', 'park']):
            keywords.extend(['outdoor-activity', 'nature', 'fresh-air'])
        
        # Category-specific keywords
        if 'entertainment' in category:
            keywords.extend(['fun', 'leisure', 'enjoyment'])
        elif 'educational' in category:
            keywords.extend(['learning', 'knowledge', 'skill-building'])
        
        return list(set(keywords))  # Remove duplicates

# Global instance
algolia_service = AlgoliaService()
