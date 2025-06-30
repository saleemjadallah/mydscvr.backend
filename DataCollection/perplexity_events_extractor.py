#!/usr/bin/env python3
"""
Perplexity AI Dubai Events Extractor
Enhanced version with improved URL extraction, social media handling, and quality metrics
"""

import json
import asyncio
from datetime import datetime, timedelta
import httpx
import os
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import sys
from loguru import logger
from dotenv import load_dotenv
import re
import hashlib
from functools import lru_cache
from tenacity import retry, stop_after_attempt, wait_exponential

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'AI_API.env'))

class ExtractionPatterns:
    """Regex patterns for enhanced data extraction"""
    
    # Date & Time Patterns
    DATE_PATTERNS = {
        'every_day': r'daily|every day|all days',
        'weekdays': r'monday to friday|weekdays|mon-fri',
        'weekends': r'friday and saturday|friday & saturday|weekends',
        'specific_days': r'every (monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
        'date_range': r'from (\d{1,2}[/-]\d{1,2}) to (\d{1,2}[/-]\d{1,2})',
        'until_date': r'until|through|till (\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
    }
    
    # Price Patterns  
    PRICE_PATTERNS = {
        'free_indicators': r'free entry|free admission|no charge|complimentary|free of charge',
        'price_range': r'AED\s?(\d+)\s?[-–]\s?(\d+)',
        'starting_price': r'from AED\s?(\d+)|starting at AED\s?(\d+)|AED\s?(\d+)\+',
        'per_person': r'AED\s?(\d+)\s?/?\s?per\s?person|pp',
        'child_price': r'children?\s?:?\s?AED\s?(\d+)|kids?\s?:?\s?AED\s?(\d+)',
        'group_discount': r'(\d+)%?\s?off\s?for\s?groups?|group\s?discount'
    }
    
    # Location Patterns
    LOCATION_PATTERNS = {
        'near_metro': r'near\s?(\w+\s?\w*)\s?metro|metro\s?station\s?:?\s?(\w+\s?\w*)',
        'landmarks': r'near|at|opposite|behind|next to\s?(Burj Khalifa|Dubai Mall|Dubai Marina|JBR|La Mer)',
        'exact_location': r'location\s?:?\s?([^,\n]+)',
        'google_maps': r'(https?://maps\.google\.com/\S+|https?://goo\.gl/maps/\S+)'
    }
    
    # Social Media Patterns
    SOCIAL_MEDIA_PATTERNS = {
        'instagram': r'(?:instagram\.com/|@)([A-Za-z0-9_\.]+)|instagram\s?:?\s?@?([A-Za-z0-9_\.]+)',
        'facebook': r'facebook\.com/([A-Za-z0-9\.\-]+)|fb\.com/([A-Za-z0-9\.\-]+)|facebook\s?:?\s?@?([A-Za-z0-9\.\-]+)',
        'twitter': r'(?:twitter\.com/|@)([A-Za-z0-9_]+)|twitter\s?:?\s?@?([A-Za-z0-9_]+)',
        'tiktok': r'(?:tiktok\.com/@|@)([A-Za-z0-9_\.]+)|tiktok\s?:?\s?@?([A-Za-z0-9_\.]+)',
        'youtube': r'youtube\.com/(?:c/|channel/|user/)?([A-Za-z0-9_\-]+)',
        'whatsapp': r'(https?://wa\.me/[A-Za-z0-9]+|https?://chat\.whatsapp\.com/[A-Za-z0-9]+)',
        'telegram': r'(?:t\.me/|telegram\.me/)([A-Za-z0-9_]+)'
    }

class DubaiEventsPerplexityExtractor:
    """
    Enhanced Perplexity extractor that uses web search to discover and extract Dubai events
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("Perplexity API key not found. Set PERPLEXITY_API_KEY environment variable.")
        
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.session_timeout = 60.0
        
        # Configure logging
        logger.add("logs/perplexity_extraction.log", rotation="10 MB", retention="7 days")
        
        # Source-specific extraction templates
        self.SOURCE_TEMPLATES = {
            'platinumlist': {
                'event_url_pattern': r'platinumlist\.net/event/(\d+)',
                'price_location': 'ticket-price-section',
                'date_format': '%d %b %Y'
            },
            'timeoutdubai': {
                'event_url_pattern': r'timeoutdubai\.com/[\w-]+/events/([\w-]+)',
                'social_media_section': 'social-links',
                'venue_extractor': 'venue-info-box'
            },
            'visitdubai': {
                'event_url_pattern': r'visitdubai\.com/en/events/([\w-]+)',
                'structured_data': True,  # Has JSON-LD
                'image_quality': 'high'
            },
            '800tickets': {
                'event_url_pattern': r'800tickets\.com/events/([\w-]+)',
                'price_reliable': True,
                'booking_available': True
            },
            'ticketmaster': {
                'event_url_pattern': r'ticketmaster\.ae/event/(\d+)',
                'has_api': True,
                'detailed_pricing': True
            }
        }
    
    def create_search_and_extract_prompt(self, search_query: str) -> Dict[str, str]:
        """
        Create a comprehensive prompt for searching and extracting Dubai events
        """
        
        system_prompt = """You are a Dubai Events specialist. Search the web and extract current Dubai events. Return ONLY valid JSON with event data and family scores. Be precise and focus on real events happening soon."""
        
        main_prompt = f"""
TASK: Search the web for Dubai events using this query: "{search_query}" and extract ALL events found - including nightlife, business, cultural, sports, dining, entertainment, and family events.

CONTEXT: This is for a comprehensive Dubai events platform. Extract every event you can find, regardless of target audience. 
We'll use family scoring and filtering on the frontend, but the database should contain ALL Dubai events.

SEARCH AND EXTRACTION REQUIREMENTS:
First, search the web for current Dubai events using the query provided. Then extract event information from the search results.

Return a JSON object with an "events" array containing ALL event information found.

For each event, extract:

1. BASIC INFORMATION:
   - title: Clear, descriptive event name
   - description: Full description from source (200-500 characters)
   - ai_summary: Create a 100-150 character engaging summary highlighting what makes it special

2. DATE & TIME:
   - start_date: ISO format (YYYY-MM-DDTHH:MM:SS) - if no specific time, use reasonable defaults
   - end_date: ISO format (if available, null if not specified)
   - duration_hours: Estimated duration (1-8 hours based on event type)
   - recurring: true/false if it's a recurring event

3. VENUE DETAILS:
   - venue_name: Official venue name
   - address: Full address if available
   - area: Dubai area (Dubai Marina, JBR, Downtown, DIFC, Jumeirah, Business Bay, etc.)
   - venue_type: "indoor"/"outdoor"/"both"
   - parking_available: true/false/unknown (infer from venue type)
   - metro_accessible: true/false/unknown (infer from area knowledge)

4. PRICING (in AED):
   - min_price: Lowest price (0 for free events)
   - max_price: Highest price (same as min if single price)
   - currency: "AED"
   - free_for_children: true/false (if children under certain age are free)
   - pricing_notes: Any special pricing details

5. AUDIENCE & SUITABILITY:
   - target_audience: ["adults", "families", "children", "teens", "seniors", "professionals", "tourists", "couples"]
   - age_restrictions: "18+", "21+", "all_ages", "children_only", etc.
   - dress_code: "casual", "smart_casual", "formal", "themed", "none"

6. FAMILY ANALYSIS (for filtering purposes):
   - family_friendly: true/false (can families with children attend?)
   - child_age_min: Minimum recommended child age (0-18, null if not suitable for children)
   - child_age_max: Maximum recommended child age (0-18, null if no upper limit)
   - stroller_accessible: true/false/unknown (based on venue and activity type)
   - requires_supervision: true/false (if children need adult supervision)
   - educational_value: "none", "low", "medium", "high"
   - child_activity_level: "passive", "low", "medium", "high"

7. EVENT CATEGORIZATION:
   - primary_category: Main category from: [
     "nightlife", "dining", "business", "networking", "cultural", "arts", "music", 
     "sports", "fitness", "entertainment", "shopping", "educational", "workshops",
     "outdoor", "adventure", "beach", "water_sports", "family", "children", 
     "festivals", "seasonal", "religious", "community", "charity", "technology",
     "health_wellness", "beauty", "fashion", "automotive", "real_estate"
   ]
   - secondary_categories: Array of additional relevant categories from the same list
   - event_type: "conference", "workshop", "concert", "party", "exhibition", "festival", 
                 "sports_event", "dining_experience", "tour", "class", "meetup", "show", etc.
   - indoor_outdoor: "indoor", "outdoor", "both"
   - special_occasion: "weekend", "holiday", "ramadan", "eid", "national_day", "valentine", "mothers_day", etc. (null if regular event)

8. ACCESSIBILITY & LOGISTICS:
   - special_needs_friendly: true/false/unknown
   - language_requirements: "arabic", "english", "bilingual", "multilingual", "none"
   - transportation_notes: Any specific transport information
   - alcohol_served: true/false/unknown (important for cultural considerations)

9. FAMILY SCORE CALCULATION (0-100, for frontend filtering):
   Calculate ONLY if family_friendly is true, otherwise set to 0:
   - Age inclusivity: Wider child age range = higher score
   - Safety & supervision: Supervised, stroller-accessible = higher score
   - Educational value: Learning opportunities = higher score
   - Duration: 1-4 hours ideal for families = higher score
   - Venue accessibility: Metro accessible, parking = higher score
   - Pricing: Free or reasonable pricing = higher score
   - Time: Weekend or evening timing = higher score
   
   For non-family events (nightlife, 18+ events, etc.), always set family_score to 0.

10. METADATA:
   - source: "Perplexity Search"
   - source_url: Original event URL if found in search results
   - event_url: Direct URL to the event page (specific event, not just domain)
   - scraped_at: Current timestamp
   - image_urls: Array of image URLs if found
   - booking_required: true/false
   - contact_info: Phone/email if available
   - ticket_links: Array of booking/ticket URLs
   - social_media: {{
       "instagram": "@handle or full URL",
       "facebook": "facebook.com/event or @handle",
       "twitter": "@handle",
       "tiktok": "@handle",
       "youtube": "channel URL",
       "whatsapp": "group link if available",
       "telegram": "channel if available"
     }}
   - quality_metrics: {{
       "extraction_confidence": 0.0-1.0,
       "data_completeness": 0.0-1.0,
       "source_reliability": "high"/"medium"/"low",
       "last_verified": timestamp,
       "extraction_method": "perplexity_search",
       "validation_warnings": []
     }}

EXTRACTION STANDARDS:
- Search comprehensively for Dubai events using the provided query
- Extract ALL events found in the search results, regardless of audience
- Include nightlife, business events, dining experiences, cultural events, sports, entertainment - everything
- Don't filter out adult-only events - mark them appropriately with family_friendly: false
- Include events without clear dates but mark them appropriately with reasonable date estimates
- Extract partial information rather than skipping events
- For unclear information, use "unknown" rather than guessing
- Focus on events happening in the next 3 months (June-August 2025) but include ongoing events and future seasonal events

RESPONSE FORMAT:
Return ONLY valid JSON in this exact structure:
{{
  "events": [
    {{
      "title": "Event Title",
      "description": "Full event description...",
      "ai_summary": "Engaging 100-150 character summary...",
      "start_date": "2025-01-15T19:00:00",
      "end_date": "2025-01-15T23:00:00",
      "duration_hours": 4,
      "recurring": false,
      "venue_name": "Venue Name",
      "address": "Full address, Dubai",
      "area": "Downtown",
      "venue_type": "indoor",
      "parking_available": true,
      "metro_accessible": true,
      "min_price": 150,
      "max_price": 300,
      "currency": "AED",
      "free_for_children": false,
      "pricing_notes": "Special pricing details",
      "target_audience": ["adults", "couples"],
      "age_restrictions": "21+",
      "dress_code": "smart_casual",
      "family_friendly": false,
      "child_age_min": null,
      "child_age_max": null,
      "stroller_accessible": false,
      "requires_supervision": false,
      "educational_value": "none",
      "child_activity_level": "passive",
      "primary_category": "nightlife",
      "secondary_categories": ["music", "dining"],
      "event_type": "concert",
      "indoor_outdoor": "indoor",
      "special_occasion": null,
      "special_needs_friendly": "unknown",
      "language_requirements": "english",
      "transportation_notes": "Valet parking available",
      "alcohol_served": true,
      "family_score": 0,
      "source": "Perplexity Search",
      "source_url": "https://example.com/event",
      "event_url": "https://example.com/event/dubai-concert-2025",
      "scraped_at": "{datetime.now().isoformat()}",
      "image_urls": ["https://example.com/image.jpg"],
      "booking_required": true,
      "contact_info": "contact@venue.com",
      "ticket_links": ["https://tickets.com/event"],
      "social_media": {{
        "instagram": "@venue",
        "facebook": "facebook.com/venueevents",
        "twitter": "@venue_dubai",
        "tiktok": "@venuedubai",
        "youtube": null,
        "whatsapp": null,
        "telegram": null
      }},
      "quality_metrics": {{
        "extraction_confidence": 0.85,
        "data_completeness": 0.80,
        "source_reliability": "high",
        "last_verified": "{datetime.now().isoformat()}",
        "extraction_method": "perplexity_search",
        "validation_warnings": []
      }}
    }}
  ],
  "extraction_metadata": {{
    "total_events_found": 1,
    "family_events_count": 0,
    "adult_events_count": 1,
    "search_query": "{search_query}",
    "processing_timestamp": "{datetime.now().isoformat()}",
    "search_quality": "high"
  }}
}}

IMPORTANT: 
- Use web search to find current Dubai events
- Extract ALL events regardless of target audience
- Use family_friendly and family_score for filtering capabilities
- Return ONLY the JSON response, no additional text
- Ensure all dates are in correct ISO format
- Family scores should only be calculated for family_friendly events
- Include metadata about the search and extraction process
"""
        
        return {
            "system_prompt": system_prompt,
            "main_prompt": main_prompt
        }
    
    def create_filtered_search_queries(self, filters: Dict[str, Any]) -> List[str]:
        """
        Generate search queries based on user filters
        
        Args:
            filters: {
                'price_range': {'min': 0, 'max': 100},
                'areas': ['Downtown', 'Marina', 'JBR'],
                'categories': ['family', 'dining', 'outdoor'],
                'dates': {'start': '2025-06-21', 'end': '2025-07-21'},
                'features': ['metro_accessible', 'free_parking', 'indoor']
            }
        
        Returns:
            List of optimized search queries based on filters
        """
        queries = []
        
        # Base query components
        base_location = "Dubai"
        year = "2025"
        
        # Process date filters
        date_terms = []
        if 'dates' in filters and filters['dates']:
            start_date = datetime.fromisoformat(filters['dates'].get('start', ''))
            end_date = datetime.fromisoformat(filters['dates'].get('end', ''))
            
            # Add month names
            months = set()
            current = start_date
            while current <= end_date:
                months.add(current.strftime('%B'))
                current = current.replace(month=current.month + 1 if current.month < 12 else 1)
            date_terms.extend(list(months))
            
            # Add weekend/weekday terms if range is short
            if (end_date - start_date).days <= 7:
                date_terms.append("this weekend")
                date_terms.append("upcoming")
        
        # Process price filters
        price_terms = []
        if 'price_range' in filters and filters['price_range']:
            min_price = filters['price_range'].get('min', 0)
            max_price = filters['price_range'].get('max', float('inf'))
            
            if max_price == 0:
                price_terms.extend(["free", "no cost", "complimentary"])
            elif max_price <= 50:
                price_terms.extend(["under 50 AED", "budget", "affordable"])
            elif max_price <= 100:
                price_terms.extend(["under 100 AED", "reasonable price"])
            elif min_price >= 500:
                price_terms.extend(["luxury", "premium", "VIP", "exclusive"])
        
        # Process area filters
        areas = filters.get('areas', [])
        
        # Process category filters
        category_mappings = {
            'family': ['family', 'kids', 'children', 'family-friendly'],
            'dining': ['restaurants', 'dining', 'food', 'brunch', 'culinary'],
            'outdoor': ['outdoor', 'beach', 'parks', 'open air'],
            'indoor': ['indoor', 'mall', 'air conditioned'],
            'cultural': ['cultural', 'heritage', 'traditional', 'museum'],
            'entertainment': ['entertainment', 'shows', 'concerts', 'performances'],
            'sports': ['sports', 'fitness', 'activities', 'gym'],
            'nightlife': ['nightlife', 'bars', 'clubs', 'late night'],
            'shopping': ['shopping', 'retail', 'markets', 'sales'],
            'business': ['business', 'networking', 'conferences', 'professional']
        }
        
        categories = filters.get('categories', [])
        category_terms = []
        for cat in categories:
            if cat in category_mappings:
                category_terms.extend(category_mappings[cat])
        
        # Process feature filters
        feature_mappings = {
            'metro_accessible': 'near metro station',
            'free_parking': 'free parking available',
            'indoor': 'indoor air conditioned',
            'outdoor': 'outdoor open air',
            'child_friendly': 'kids children family',
            'wheelchair_accessible': 'wheelchair accessible special needs',
            'alcohol_free': 'no alcohol family friendly'
        }
        
        features = filters.get('features', [])
        feature_terms = []
        for feat in features:
            if feat in feature_mappings:
                feature_terms.append(feature_mappings[feat])
        
        # Generate queries combining different filter combinations
        
        # Area-based queries
        if areas:
            for area in areas[:3]:  # Limit to top 3 areas
                query_parts = [base_location, area, "events"]
                
                if category_terms:
                    query_parts.extend(category_terms[:2])
                if price_terms:
                    query_parts.append(price_terms[0])
                if date_terms:
                    query_parts.append(date_terms[0])
                if feature_terms:
                    query_parts.append(feature_terms[0])
                
                query_parts.append(year)
                queries.append(" ".join(query_parts))
        
        # Category-based queries
        if categories:
            for cat in categories[:3]:  # Limit to top 3 categories
                query_parts = [base_location]
                
                if cat in category_mappings:
                    query_parts.extend(category_mappings[cat][:2])
                
                query_parts.append("events")
                
                if price_terms:
                    query_parts.append(price_terms[0])
                if date_terms:
                    query_parts.append(date_terms[0])
                if areas:
                    query_parts.append(areas[0])
                
                query_parts.append(year)
                queries.append(" ".join(query_parts))
        
        # Price-focused queries
        if price_terms:
            query_parts = [base_location, "events"] + price_terms[:2]
            
            if category_terms:
                query_parts.append(category_terms[0])
            if date_terms:
                query_parts.append(date_terms[0])
            
            queries.append(" ".join(query_parts))
        
        # Feature-focused queries
        if feature_terms:
            for feature in feature_terms[:2]:
                query_parts = [base_location, "events", feature]
                
                if category_terms:
                    query_parts.append(category_terms[0])
                if areas:
                    query_parts.append(areas[0])
                
                queries.append(" ".join(query_parts))
        
        # Default query if no specific filters
        if not queries:
            query_parts = [base_location, "events", "activities"]
            if date_terms:
                query_parts.extend(date_terms[:2])
            query_parts.append(year)
            queries.append(" ".join(query_parts))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique_queries.append(q)
        
        logger.info(f"📋 Generated {len(unique_queries)} filtered search queries from filters: {filters}")
        
        return unique_queries[:10]  # Limit to 10 queries max
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for better duplicate detection
        """
        if not text:
            return ""
        
        import re
        
        # Convert to lowercase
        normalized = text.lower().strip()
        
        # Remove common variations and formatting
        normalized = re.sub(r'\s+', ' ', normalized)  # Multiple spaces to single
        normalized = re.sub(r'[^\w\s-]', '', normalized)  # Remove special chars except hyphens
        normalized = re.sub(r'\b(the|a|an|at|in|on|for|with|by)\b', '', normalized)  # Remove articles/prepositions
        normalized = re.sub(r'\b(dubai|uae|united arab emirates)\b', '', normalized)  # Remove location redundancy
        normalized = re.sub(r'\b(event|events|activity|activities|experience|experiences)\b', '', normalized)  # Remove generic terms
        normalized = re.sub(r'\b(2024|2025|2026)\b', '', normalized)  # Remove years
        normalized = re.sub(r'\s+', ' ', normalized).strip()  # Clean up extra spaces
        
        return normalized
    
    def extract_price_info(self, text: str) -> Dict[str, Any]:
        """
        Extract price information using regex patterns
        """
        price_info = {
            'min_price': 0,
            'max_price': 0,
            'is_free': False,
            'pricing_notes': []
        }
        
        # Check for free indicators
        if re.search(ExtractionPatterns.PRICE_PATTERNS['free_indicators'], text, re.IGNORECASE):
            price_info['is_free'] = True
            price_info['pricing_notes'].append("Free entry")
            return price_info
        
        # Extract price range
        range_match = re.search(ExtractionPatterns.PRICE_PATTERNS['price_range'], text)
        if range_match:
            price_info['min_price'] = int(range_match.group(1))
            price_info['max_price'] = int(range_match.group(2))
        
        # Extract starting price
        starting_match = re.search(ExtractionPatterns.PRICE_PATTERNS['starting_price'], text)
        if starting_match:
            price = int(next(g for g in starting_match.groups() if g))
            price_info['min_price'] = price
            if not price_info['max_price']:
                price_info['max_price'] = price * 2  # Estimate
        
        # Extract per person price
        pp_match = re.search(ExtractionPatterns.PRICE_PATTERNS['per_person'], text)
        if pp_match:
            price = int(pp_match.group(1))
            if not price_info['min_price']:
                price_info['min_price'] = price
                price_info['max_price'] = price
        
        # Extract child price
        child_match = re.search(ExtractionPatterns.PRICE_PATTERNS['child_price'], text)
        if child_match:
            child_price = int(next(g for g in child_match.groups() if g))
            price_info['pricing_notes'].append(f"Children: AED {child_price}")
        
        return price_info
    
    def extract_date_info(self, text: str) -> Dict[str, Any]:
        """
        Extract date and timing information using regex patterns
        """
        date_info = {
            'recurring': False,
            'specific_days': [],
            'date_notes': []
        }
        
        # Check for daily events
        if re.search(ExtractionPatterns.DATE_PATTERNS['every_day'], text, re.IGNORECASE):
            date_info['recurring'] = True
            date_info['date_notes'].append("Daily event")
        
        # Check for weekdays
        if re.search(ExtractionPatterns.DATE_PATTERNS['weekdays'], text, re.IGNORECASE):
            date_info['recurring'] = True
            date_info['specific_days'] = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        
        # Check for weekends
        if re.search(ExtractionPatterns.DATE_PATTERNS['weekends'], text, re.IGNORECASE):
            date_info['recurring'] = True
            date_info['specific_days'] = ['friday', 'saturday']
        
        # Check for specific days
        specific_match = re.findall(ExtractionPatterns.DATE_PATTERNS['specific_days'], text, re.IGNORECASE)
        if specific_match:
            date_info['recurring'] = True
            date_info['specific_days'].extend([day.lower() for day in specific_match])
        
        return date_info
    
    def extract_location_info(self, text: str) -> Dict[str, Any]:
        """
        Extract location and venue information using regex patterns
        """
        location_info = {
            'metro_station': None,
            'landmarks': [],
            'google_maps_url': None,
            'location_notes': []
        }
        
        # Extract metro station
        metro_match = re.search(ExtractionPatterns.LOCATION_PATTERNS['near_metro'], text, re.IGNORECASE)
        if metro_match:
            station = next(g for g in metro_match.groups() if g)
            location_info['metro_station'] = station
            location_info['location_notes'].append(f"Near {station} Metro")
        
        # Extract landmarks
        landmarks = re.findall(ExtractionPatterns.LOCATION_PATTERNS['landmarks'], text, re.IGNORECASE)
        if landmarks:
            location_info['landmarks'] = landmarks
        
        # Extract Google Maps URL
        maps_match = re.search(ExtractionPatterns.LOCATION_PATTERNS['google_maps'], text)
        if maps_match:
            location_info['google_maps_url'] = maps_match.group(1)
        
        return location_info
    
    def extract_social_media(self, text: str) -> Dict[str, Optional[str]]:
        """
        Extract social media handles and URLs using regex patterns
        """
        social_media = {
            'instagram': None,
            'facebook': None,
            'twitter': None,
            'tiktok': None,
            'youtube': None,
            'whatsapp': None,
            'telegram': None
        }
        
        for platform, pattern in ExtractionPatterns.SOCIAL_MEDIA_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Get the first non-None group
                handle = next((g for g in match.groups() if g), None)
                if handle:
                    # Format appropriately
                    if platform in ['whatsapp', 'telegram'] and 'http' in text[match.start():match.end()]:
                        social_media[platform] = text[match.start():match.end()]
                    elif platform == 'youtube' and 'youtube.com' in text[match.start():match.end()]:
                        social_media[platform] = text[match.start():match.end()]
                    else:
                        social_media[platform] = f"@{handle}" if not handle.startswith('@') else handle
        
        return social_media
    
    def calculate_extraction_confidence(self, event: Dict) -> float:
        """
        Calculate confidence score for extracted event data
        
        Returns:
            Score between 0.0 and 1.0 indicating extraction confidence
        """
        confidence_score = 0.0
        weights = {
            'critical': 0.4,    # Title, description, date, venue
            'important': 0.3,   # Price, category, location details
            'helpful': 0.2,     # Social media, images, contact
            'extra': 0.1        # Additional metadata
        }
        
        # Critical fields (40% weight)
        critical_fields = ['title', 'description', 'start_date', 'venue_name']
        critical_score = sum(1 for field in critical_fields if event.get(field)) / len(critical_fields)
        confidence_score += critical_score * weights['critical']
        
        # Important fields (30% weight)
        important_fields = ['min_price', 'max_price', 'primary_category', 'area', 'event_url']
        important_score = sum(1 for field in important_fields if event.get(field)) / len(important_fields)
        confidence_score += important_score * weights['important']
        
        # Helpful fields (20% weight)
        helpful_score = 0
        if event.get('social_media'):
            social_count = sum(1 for v in event['social_media'].values() if v)
            helpful_score += social_count / 7 * 0.5
        if event.get('image_urls') and len(event['image_urls']) > 0:
            helpful_score += 0.3
        if event.get('contact_info'):
            helpful_score += 0.2
        confidence_score += helpful_score * weights['helpful']
        
        # Extra fields (10% weight)
        extra_fields = ['booking_required', 'ticket_links', 'parking_available', 'metro_accessible']
        extra_score = sum(1 for field in extra_fields if field in event and event[field] is not None) / len(extra_fields)
        confidence_score += extra_score * weights['extra']
        
        return round(confidence_score, 2)
    
    def calculate_data_completeness(self, event: Dict) -> float:
        """
        Calculate how complete the event data is
        
        Returns:
            Score between 0.0 and 1.0 indicating data completeness
        """
        total_fields = 0
        filled_fields = 0
        
        # Define all expected fields
        expected_fields = [
            'title', 'description', 'ai_summary', 'start_date', 'end_date',
            'venue_name', 'address', 'area', 'min_price', 'max_price',
            'primary_category', 'secondary_categories', 'event_url', 'source_url',
            'image_urls', 'family_friendly', 'family_score', 'target_audience',
            'age_restrictions', 'dress_code', 'parking_available', 'metro_accessible',
            'special_needs_friendly', 'booking_required', 'contact_info', 'ticket_links'
        ]
        
        for field in expected_fields:
            total_fields += 1
            if field in event and event[field] is not None:
                # Check if the field has meaningful content
                if isinstance(event[field], str) and event[field].strip():
                    filled_fields += 1
                elif isinstance(event[field], (list, dict)) and len(event[field]) > 0:
                    filled_fields += 1
                elif isinstance(event[field], (int, float, bool)):
                    filled_fields += 1
        
        # Check social media completeness separately
        if event.get('social_media'):
            social_filled = sum(1 for v in event['social_media'].values() if v)
            if social_filled > 0:
                filled_fields += 1
            total_fields += 1
        
        return round(filled_fields / total_fields if total_fields > 0 else 0, 2)
    
    def assess_source_reliability(self, source_url: str) -> str:
        """
        Assess the reliability of the event source
        
        Returns:
            "high", "medium", or "low" reliability rating
        """
        if not source_url:
            return "low"
        
        high_reliability_domains = [
            'visitdubai.com', 'dubaiculture.gov.ae', 'dubai.ae',
            'timeoutdubai.com', 'platinumlist.net', 'ticketmaster.ae',
            '800tickets.com', 'dubaioperahouse.com', 'coca-cola-arena.com'
        ]
        
        medium_reliability_domains = [
            'eventbrite.com', 'facebook.com/events', 'instagram.com',
            'whatson.ae', 'lovindubai.com', 'gulfnews.com',
            'khaleejtimes.com', 'thenationalnews.com'
        ]
        
        # Check domain
        for domain in high_reliability_domains:
            if domain in source_url.lower():
                return "high"
        
        for domain in medium_reliability_domains:
            if domain in source_url.lower():
                return "medium"
        
        return "low"
    
    def generate_quality_metrics(self, event: Dict, source_url: str = None) -> Dict[str, Any]:
        """
        Generate comprehensive quality metrics for an event
        """
        metrics = {
            "extraction_confidence": self.calculate_extraction_confidence(event),
            "data_completeness": self.calculate_data_completeness(event),
            "source_reliability": self.assess_source_reliability(source_url or event.get('source_url', '')),
            "last_verified": datetime.now().isoformat(),
            "extraction_method": "perplexity_search",
            "validation_warnings": []
        }
        
        # Add validation warnings
        if not event.get('event_url'):
            metrics['validation_warnings'].append("No direct event URL found")
        
        if event.get('start_date'):
            try:
                start_date = datetime.fromisoformat(event['start_date'].replace('Z', '+00:00'))
                if start_date < datetime.now():
                    metrics['validation_warnings'].append("Event date appears to be in the past")
            except:
                metrics['validation_warnings'].append("Invalid date format")
        
        if event.get('min_price', 0) > event.get('max_price', 0) and event.get('max_price', 0) > 0:
            metrics['validation_warnings'].append("Min price greater than max price")
        
        if not event.get('image_urls'):
            metrics['validation_warnings'].append("No event images found")
        
        return metrics
    
    @lru_cache(maxsize=100)
    def get_cached_search_hash(self, query: str) -> str:
        """
        Generate a hash for caching search results
        """
        return hashlib.md5(query.encode()).hexdigest()
    
    async def batch_search_events(self, queries: List[str], batch_size: int = 5) -> List[Dict[str, Any]]:
        """
        Process multiple search queries in batches to optimize API usage
        """
        all_events = []
        
        for i in range(0, len(queries), batch_size):
            batch = queries[i:i+batch_size]
            batch_tasks = []
            
            for query in batch:
                # Check cache first
                query_hash = self.get_cached_search_hash(query)
                if hasattr(self, '_search_cache') and query_hash in self._search_cache:
                    logger.info(f"📦 Using cached results for: {query}")
                    all_events.extend(self._search_cache[query_hash])
                else:
                    batch_tasks.append(self.search_with_retry(query))
            
            if batch_tasks:
                # Process batch concurrently
                results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for result, query in zip(results, [q for q in batch if self.get_cached_search_hash(q) not in getattr(self, '_search_cache', {})]):
                    if isinstance(result, Exception):
                        logger.error(f"❌ Error in batch search for '{query}': {result}")
                    elif result.get('events'):
                        # Cache the results
                        if not hasattr(self, '_search_cache'):
                            self._search_cache = {}
                        self._search_cache[self.get_cached_search_hash(query)] = result['events']
                        all_events.extend(result['events'])
            
            # Add delay between batches
            if i + batch_size < len(queries):
                await asyncio.sleep(2)
        
        return all_events
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def search_with_retry(self, query: str) -> Dict[str, Any]:
        """
        Retry failed searches with exponential backoff
        """
        return await self.search_and_extract_events(query)
    
    async def search_and_extract_events(self, search_query: str) -> Dict[str, Any]:
        """
        Search for events using Perplexity and extract structured data
        """
        logger.info(f"🔍 Searching for Dubai events: {search_query}")
        
        prompts = self.create_search_and_extract_prompt(search_query)
        
        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system", 
                    "content": prompts["system_prompt"]
                },
                {
                    "role": "user", 
                    "content": prompts["main_prompt"]
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.1,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "events": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"},
                                        "description": {"type": "string"},
                                        "ai_summary": {"type": "string"},
                                        "start_date": {"type": "string"},
                                        "end_date": {"type": ["string", "null"]},
                                        "venue_name": {"type": "string"},
                                        "area": {"type": "string"},
                                        "min_price": {"type": "number"},
                                        "max_price": {"type": "number"},
                                        "family_friendly": {"type": "boolean"},
                                        "family_score": {"type": "number"},
                                        "primary_category": {"type": "string"},
                                        "source": {"type": "string"},
                                        "event_url": {"type": ["string", "null"]},
                                        "social_media": {
                                            "type": "object",
                                            "properties": {
                                                "instagram": {"type": ["string", "null"]},
                                                "facebook": {"type": ["string", "null"]},
                                                "twitter": {"type": ["string", "null"]},
                                                "tiktok": {"type": ["string", "null"]},
                                                "youtube": {"type": ["string", "null"]},
                                                "whatsapp": {"type": ["string", "null"]},
                                                "telegram": {"type": ["string", "null"]}
                                            }
                                        },
                                        "quality_metrics": {
                                            "type": "object",
                                            "properties": {
                                                "extraction_confidence": {"type": "number"},
                                                "data_completeness": {"type": "number"},
                                                "source_reliability": {"type": "string"},
                                                "last_verified": {"type": "string"},
                                                "extraction_method": {"type": "string"},
                                                "validation_warnings": {"type": "array", "items": {"type": "string"}}
                                            }
                                        }
                                    },
                                    "required": ["title", "description", "ai_summary", "start_date", "venue_name", "area", "family_friendly", "family_score", "primary_category", "source"]
                                }
                            },
                            "extraction_metadata": {
                                "type": "object",
                                "properties": {
                                    "total_events_found": {"type": "number"},
                                    "search_query": {"type": "string"},
                                    "processing_timestamp": {"type": "string"}
                                }
                            }
                        },
                        "required": ["events", "extraction_metadata"]
                    }
                }
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.session_timeout) as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    
                    logger.info(f"📝 Perplexity response content (first 500 chars): {content[:500]}")
                    
                    try:
                        # Try to find JSON in the response if it's wrapped in text
                        if not content.strip().startswith('{'):
                            # Look for JSON block in the response
                            import re
                            json_match = re.search(r'\{.*\}', content, re.DOTALL)
                            if json_match:
                                content = json_match.group(0)
                                logger.info("🔧 Extracted JSON from text response")
                            else:
                                logger.error(f"❌ No JSON found in response: {content}")
                                return {"events": [], "extraction_metadata": {"error": "No JSON in response", "raw_content": content}}
                        
                        events_data = json.loads(content)
                        logger.info(f"✅ Successfully extracted {len(events_data.get('events', []))} events")
                        return events_data
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Failed to parse JSON response: {e}")
                        logger.error(f"Raw content: {content}")
                        return {"events": [], "extraction_metadata": {"error": "JSON parse error", "raw_content": content}}
                        
                else:
                    logger.error(f"❌ Perplexity API error: {response.status_code} - {response.text}")
                    raise Exception(f"Perplexity API error: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.error(f"❌ Error during event extraction: {e}")
            return {"events": [], "extraction_metadata": {"error": str(e)}}
    
    async def discover_events_by_categories(self) -> List[Dict[str, Any]]:
        """
        Search for events across multiple categories and sources with improved time targeting
        """
        # Get current date for dynamic queries
        current_date = datetime.now()
        next_month = current_date.replace(month=current_date.month + 1 if current_date.month < 12 else 1)
        
        search_queries = [
            # Time-specific family events (broader timeframes)
            f"Dubai family events activities kids children June July 2025 summer holidays",
            f"Dubai family events activities kids children next month {next_month.strftime('%B')} 2025",
            "Dubai family events activities kids children upcoming weekend holidays",
            
            # Kids & Family specific venues and activities
            "Dubai kids play areas indoor playground Bounce Hub Zero trampoline parks 2025",
            "Dubai family restaurants with play areas kids menu children entertainment 2025",
            "Dubai beach events for kids children activities Jumeirah Beach Kite Beach family 2025",
            "Dubai theme parks attractions Motiongate Bollywood Parks Legoland IMG Worlds 2025",
            "Dubai kids clubs activities children programs hotels resorts family fun 2025",
            "Dubai swimming pools kids water play splash pads family pools 2025",
            "Dubai parks gardens Green Planet Miracle Garden Butterfly Garden kids 2025",
            "Dubai kids workshops art painting pottery cooking classes children activities 2025",
            "Dubai family brunch kids menu entertainment children activities restaurants 2025",
            "Dubai cinema kids movies family films children screenings entertainment 2025",
            "Dubai bowling skating ice skating kids activities family entertainment centers 2025",
            "Dubai kids birthday party venues children celebration entertainment packages 2025",
            "Dubai family-friendly malls kids areas children entertainment shopping 2025",
            "Dubai petting zoos farms animals kids experiences children activities 2025",
            "Dubai sports activities for kids football tennis swimming classes children 2025",
            "Dubai storytelling sessions kids libraries bookstores children reading events 2025",
            "Dubai science experiments kids STEM activities children learning discovery 2025",
            "Dubai farm visits camel rides horse riding kids animal experiences 2025",
            "Dubai kids yoga baby swimming toddler classes children wellness activities 2025",
            "Dubai family festivals cultural events Ramadan Eid children traditional 2025",
            
            # Venue-specific searches for more unique events
            "Dubai Mall events activities shows performances exhibitions 2025",
            "Mall of Emirates events activities entertainment kids shows 2025",
            "Global Village Dubai events shows attractions 2025",
            "Dubai Marina events activities restaurants beach clubs 2025",
            "Downtown Dubai events Burj Khalifa Dubai Fountain activities 2025",
            "JBR Jumeirah Beach Residence events beach activities restaurants 2025",
            "City Walk Dubai events restaurants activities entertainment family 2025",
            "La Mer Dubai events beach activities restaurants water sports family 2025",
            "Bluewaters Island Dubai events Ain Dubai activities restaurants 2025",
            "Dubai Festival City events mall activities entertainment family 2025",
            "Al Seef Dubai Creek events heritage cultural activities family 2025",
            "Expo City Dubai events exhibitions activities entertainment family 2025",
            
            # Seasonal and holiday events (more specific)
            "Dubai summer events activities June July August 2025 indoor air conditioning",
            "Dubai Eid celebrations events activities 2025 family traditions",
            "Dubai National Day events celebrations December 2025",
            
            # Category-specific with venues
            "Dubai nightlife bars clubs Zero Gravity White Dubai Soho Garden 2025",
            "Dubai cultural events Alserkal Avenue DIFC Art Centre Opera House 2025",
            "Dubai sports events Dubai Sports City golf tennis motorsports 2025",
            "Dubai business events DIFC World Trade Centre conferences networking 2025",
            
            # Dining and food (specific venues/areas)
            "Dubai dining food festivals City Walk La Mer Bluewaters restaurants 2025",
            "Dubai brunch events Friday brunch Saturday brunch luxury hotels 2025",
            "Dubai bottomless brunch weekend brunch unlimited drinks prosecco mimosas 2025",
            "Dubai brunch deals offers Four Seasons Atlantis Jumeirah hotels restaurants 2025",
            
            # Entertainment and shows
            "Dubai entertainment shows Dubai Opera Coca Cola Arena theater concerts 2025",
            "Dubai comedy shows Stand Up Comedy Dubai theater performances 2025",
            
            # Shopping and lifestyle
            "Dubai shopping events festivals DSF Dubai Shopping Festival sales 2025",
            "Dubai fashion events fashion week shows designer exhibitions 2025",
            
            # Water and beach activities
            "Dubai beach events Jumeirah Beach La Mer Kite Beach water sports 2025",
            "Dubai water parks Atlantis Aquaventure Wild Wadi Laguna events 2025",
            
            # Educational and workshops
            "Dubai educational workshops museums science centre children learning 2025",
            "Dubai art workshops classes creative activities pottery painting 2025",
            
            # Luxury and exclusive
            "Dubai luxury events VIP experiences private dining exclusive parties 2025",
            "Dubai rooftop events skybar restaurants panoramic views 2025",
            
            # Government & Official Sources
            "site:dubaiculture.gov.ae upcoming events exhibitions",
            "site:visitdubai.com events calendar June July August 2025",
            "Dubai Municipality events public activities cultural celebrations 2025",
            "site:dubaicalendar.ae upcoming events shows exhibitions 2025",
            
            # Venue-Specific Enhanced Searches  
            "Coca Cola Arena Dubai concerts shows tickets schedule 2025",
            "Dubai Opera performances schedule booking tickets 2025",
            "La Perle Dubai shows timings tickets discount offers 2025",
            "Dubai World Trade Centre exhibitions conferences events calendar 2025",
            "Dubai International Convention Centre events exhibitions 2025",
            "Madinat Jumeirah events amphitheatre shows performances 2025",
            
            # Ticket Platform Searches
            "site:ticketmaster.ae Dubai events concerts shows",
            "site:platinumlist.net Dubai upcoming events tickets",
            "site:800tickets.com Dubai shows entertainment",
            "site:virginmegastore.ae Dubai events tickets",
            "site:dubaitickets.com upcoming events shows",
            
            # Social Media Event Discovery
            "Dubai events Instagram popular trending viral 2025",
            "Dubai weekend activities TikTok viral spots experiences",
            "Dubai Facebook events this weekend upcoming",
            "#DubaiEvents #MyDubai #VisitDubai trending activities",
            
            # Price-Filtered Searches
            "Dubai free events this weekend families activities no cost",
            "Dubai events under 50 AED budget affordable",
            "Dubai events under 100 AED families kids affordable",
            "Dubai luxury exclusive events VIP premium experiences",
            "Dubai events free entry complimentary admission 2025",
            
            # Location-Based Enhanced Searches
            "Dubai Marina Walk events waterfront dining entertainment 2025",
            "JBR Beach events activities outdoor restaurants nightlife 2025",
            "Old Dubai Deira Creek events cultural heritage souks 2025",
            "Business Bay Dubai events after work happy hour networking 2025",
            "Palm Jumeirah events beach clubs restaurants activities 2025",
            "Dubai Hills events community activities family weekend 2025",
            "Jumeirah events beach activities luxury dining 2025",
            "Al Barsha events community family activities 2025"
        ]
        
        # Use batch search for better performance
        logger.info(f"🚀 Starting batch search for {len(search_queries)} queries")
        all_events = await self.batch_search_events(search_queries, batch_size=5)
        
        # Enhanced duplicate removal with multiple strategies
        unique_events = []
        seen_events = set()
        
        for event in all_events:
            # Strategy 1: Normalize title for comparison
            normalized_title = self._normalize_text(event.get('title', ''))
            normalized_venue = self._normalize_text(event.get('venue_name', ''))
            
            # Strategy 2: Create multiple duplicate detection keys
            keys_to_check = [
                # Primary key: normalized title + venue
                f"{normalized_title}-{normalized_venue}",
                # Secondary key: title + venue + date (for recurring events)
                f"{normalized_title}-{normalized_venue}-{event.get('start_date', '')[:10]}",
                # Tertiary key: description similarity (first 100 chars)
                f"{normalized_title}-{event.get('description', '')[:100].lower().strip()}"
            ]
            
            # Check if any key indicates this is a duplicate
            is_duplicate = any(key in seen_events for key in keys_to_check if key.strip())
            
            if not is_duplicate:
                # Add all keys to seen_events
                for key in keys_to_check:
                    if key.strip():
                        seen_events.add(key)
                # Add quality metrics to each unique event
                event['quality_metrics'] = self.generate_quality_metrics(event)
                unique_events.append(event)
        
        logger.info(f"🔄 Removed {len(all_events) - len(unique_events)} duplicates from {len(all_events)} total events")
        
        # Log quality statistics
        if unique_events:
            avg_confidence = sum(e['quality_metrics']['extraction_confidence'] for e in unique_events) / len(unique_events)
            avg_completeness = sum(e['quality_metrics']['data_completeness'] for e in unique_events) / len(unique_events)
            high_quality = sum(1 for e in unique_events if e['quality_metrics']['source_reliability'] == 'high')
            
            logger.info(f"📊 Quality Metrics:")
            logger.info(f"   Average Confidence: {avg_confidence:.2f}")
            logger.info(f"   Average Completeness: {avg_completeness:.2f}")
            logger.info(f"   High Reliability Sources: {high_quality}/{len(unique_events)}")
        
        logger.info(f"✅ Discovered {len(unique_events)} unique events from {len(search_queries)} search queries")
        
        return unique_events
    
    async def search_events_with_filters(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Search for events using user-provided filters
        
        Args:
            filters: Dictionary containing filter criteria
        
        Returns:
            List of unique events matching the filters
        """
        # Generate optimized queries based on filters
        search_queries = self.create_filtered_search_queries(filters)
        
        # Use batch search for efficiency
        logger.info(f"🎯 Searching with filters: {filters}")
        all_events = await self.batch_search_events(search_queries, batch_size=3)
        
        # Remove duplicates
        unique_events = []
        seen_events = set()
        
        for event in all_events:
            normalized_key = f"{self._normalize_text(event.get('title', ''))}-{self._normalize_text(event.get('venue_name', ''))}"
            
            if normalized_key not in seen_events and normalized_key.strip():
                seen_events.add(normalized_key)
                
                # Add quality metrics
                event['quality_metrics'] = self.generate_quality_metrics(event)
                
                # Apply additional filtering based on criteria
                if self._event_matches_filters(event, filters):
                    unique_events.append(event)
        
        logger.info(f"✅ Found {len(unique_events)} events matching filters")
        
        return unique_events
    
    def _event_matches_filters(self, event: Dict, filters: Dict[str, Any]) -> bool:
        """
        Check if an event matches the provided filters
        """
        # Price filter
        if 'price_range' in filters:
            min_filter = filters['price_range'].get('min', 0)
            max_filter = filters['price_range'].get('max', float('inf'))
            
            event_min = event.get('min_price', 0)
            event_max = event.get('max_price', event_min)
            
            if event_max < min_filter or event_min > max_filter:
                return False
        
        # Area filter
        if 'areas' in filters and filters['areas']:
            event_area = event.get('area', '').lower()
            if not any(area.lower() in event_area for area in filters['areas']):
                return False
        
        # Category filter
        if 'categories' in filters and filters['categories']:
            event_cat = event.get('primary_category', '').lower()
            if not any(cat.lower() in event_cat for cat in filters['categories']):
                return False
        
        # Date filter
        if 'dates' in filters and filters['dates']:
            try:
                event_date = datetime.fromisoformat(event.get('start_date', '').replace('Z', '+00:00'))
                start_filter = datetime.fromisoformat(filters['dates'].get('start', ''))
                end_filter = datetime.fromisoformat(filters['dates'].get('end', ''))
                
                if event_date < start_filter or event_date > end_filter:
                    return False
            except:
                pass
        
        return True

# Example usage and testing
async def main():
    """
    Test the Perplexity events extractor
    """
    try:
        # Initialize extractor
        extractor = DubaiEventsPerplexityExtractor()
        
        # Test single search
        logger.info("🚀 Testing single event search...")
        result = await extractor.search_and_extract_events("Dubai family events activities kids children this weekend")
        
        if result.get("events"):
            logger.info(f"✅ Found {len(result['events'])} events in test search")
            
            # Print sample events with quality metrics
            for i, event in enumerate(result["events"][:3], 1):
                logger.info(f"Event {i}: {event.get('title')}")
                logger.info(f"  - Family Score: {event.get('family_score', 0)}")
                if event.get('quality_metrics'):
                    logger.info(f"  - Extraction Confidence: {event['quality_metrics']['extraction_confidence']}")
                    logger.info(f"  - Data Completeness: {event['quality_metrics']['data_completeness']}")
        
        # Test filtered search
        logger.info("🚀 Testing filtered event search...")
        filters = {
            'price_range': {'min': 0, 'max': 100},
            'areas': ['Marina', 'JBR'],
            'categories': ['family', 'outdoor'],
            'dates': {'start': '2025-06-21', 'end': '2025-07-21'}
        }
        
        filtered_events = await extractor.search_events_with_filters(filters)
        logger.info(f"✅ Found {len(filtered_events)} events matching filters")
        
        # Test comprehensive discovery
        logger.info("🚀 Testing comprehensive event discovery...")
        all_events = await extractor.discover_events_by_categories()
        
        # Analyze results
        family_events = [e for e in all_events if e.get('family_friendly', False)]
        adult_events = [e for e in all_events if not e.get('family_friendly', False)]
        
        logger.info(f"📊 Discovery Results:")
        logger.info(f"   Total Events: {len(all_events)}")
        logger.info(f"   Family Events: {len(family_events)}")
        logger.info(f"   Adult Events: {len(adult_events)}")
        
        # Save results for inspection
        output_file = Path("data/perplexity_events_sample.json")
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_events": len(all_events),
                "family_events_count": len(family_events),
                "adult_events_count": len(adult_events),
                "events": all_events[:20]  # Save first 20 events as sample
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Sample results saved to {output_file}")
        
        return all_events
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return []

if __name__ == "__main__":
    asyncio.run(main()) 