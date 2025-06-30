# Perplexity AI Dubai Events Extractor - Enhancement Implementation Prompt

## Context
We have an existing Perplexity AI Dubai Events Extractor with a solid foundation that:
- Extracts 40+ event fields including comprehensive event details
- Implements family-friendly scoring (0-100)
- Handles duplicate detection with multiple strategies
- Searches across multiple event categories
- Returns structured JSON with validation

## Task: Enhance the Existing Extractor

Please enhance the current `DubaiEventsPerplexityExtractor` class by adding the following capabilities while maintaining all existing functionality:

### 1. Enhanced Event URL and Social Media Extraction

**Add to the existing metadata section:**
```python
# In the METADATA section of the prompt, enhance the existing fields:
- event_url: Direct URL to the event page (not just source_url)
- social_media: Expand from simple handles to structured format:
  {
    "instagram": "@handle or full URL",
    "facebook": "facebook.com/event or @handle",
    "twitter": "@handle",
    "tiktok": "@handle", 
    "youtube": "channel URL",
    "whatsapp": "group link if available",
    "telegram": "channel if available"
  }
```

**Implementation Requirements:**
- Extract event-specific URLs, not just domain URLs
- Capture all available social media links mentioned
- Handle various social media URL formats
- Set to null if not found rather than omitting

### 2. Scale the Operation with Enhanced Search Queries

**Add these new search query categories to `discover_events_by_categories()`:**
```python
# Government & Official Sources
"site:dubaiculture.gov.ae upcoming events exhibitions",
"site:visitdubai.com events calendar {current_month} {next_month}",
"Dubai Municipality events public activities",

# Venue-Specific Searches  
"Coca Cola Arena Dubai concerts shows {next_month}",
"Dubai Opera performances schedule booking",
"La Perle Dubai shows timings tickets",
"Dubai World Trade Centre exhibitions conferences",

# Ticket Platform Searches
"site:ticketmaster.ae Dubai events",
"site:platinumlist.net Dubai upcoming",
"site:800tickets.com Dubai shows",

# Social Media Event Discovery
"Dubai events Instagram popular trending",
"Dubai weekend activities TikTok viral",

# Price-Filtered Searches
"Dubai free events this weekend families",
"Dubai events under 50 AED budget",
"Dubai luxury exclusive events VIP",

# Location-Based Searches
"Dubai Marina events waterfront dining",
"JBR Beach events activities outdoor",
"Old Dubai Deira events cultural heritage",
"Business Bay Dubai events after work"
```

### 3. Implement Filter-to-Query System

**Add a new method `create_filtered_search_queries()`:**
```python
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
    # Implementation: Generate targeted queries like:
    # "Dubai Downtown family events free parking"
    # "Dubai Marina dining under 100 AED"
    # "Dubai indoor events metro accessible July 2025"
```

### 4. Enhanced Data Quality Patterns

**Add these extraction patterns to improve data quality:**

```python
# Enhanced extraction patterns to add:
class ExtractionPatterns:
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
```

**Add validation and confidence scoring:**
```python
def calculate_extraction_confidence(self, event: Dict) -> float:
    """
    Calculate confidence score for extracted event data
    
    Returns:
        Score between 0.0 and 1.0 indicating extraction confidence
    """
    # Check completeness of critical fields
    # Validate date formats
    # Check price reasonableness
    # Verify location data
    # Return confidence score
```

### 5. Add Quality Metrics Collection

**Add to each extracted event:**
```python
"quality_metrics": {
    "extraction_confidence": 0.95,  # How confident the extraction is
    "data_completeness": 0.80,      # Percentage of fields filled
    "source_reliability": "high",    # Source credibility rating
    "last_verified": "2025-06-21T10:00:00",
    "extraction_method": "perplexity_search",
    "validation_warnings": []        # Any data quality issues
}
```

### 6. Implement Source-Specific Extraction Templates

**Add source detection and custom extraction:**
```python
SOURCE_TEMPLATES = {
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
    }
}
```

### 7. Performance Optimizations

**Add these optimizations:**
```python
# Batch processing for multiple queries
async def batch_search_events(self, queries: List[str], batch_size: int = 5):
    """Process multiple search queries in batches to optimize API usage"""
    
# Caching for duplicate queries
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_search_results(self, query_hash: str):
    """Cache search results to avoid duplicate API calls"""
    
# Smart retry logic for failed extractions
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def search_with_retry(self, query: str):
    """Retry failed searches with exponential backoff"""
```

## Expected Deliverables

1. **Enhanced `DubaiEventsPerplexityExtractor` class** with all new methods and patterns
2. **Updated prompt templates** incorporating new extraction requirements
3. **Maintained backward compatibility** with existing event structure
4. **Comprehensive error handling** for new features
5. **Updated logging** to track new metrics and extraction quality

## Code Structure Requirements

- Keep all existing functionality intact
- Add new methods to the existing class
- Enhance the existing prompts without breaking current extraction
- Use async/await patterns consistently
- Follow the existing logging patterns with loguru
- Maintain the JSON schema validation

## Testing Requirements

Include test cases for:
- Event URL extraction from various source formats
- Social media handle extraction and normalization  
- Filter-based query generation
- Quality metric calculation
- Source-specific template matching

## Example Enhanced Event Output

```json
{
  "title": "Dubai Food Festival at La Mer Beach",
  "description": "Annual food festival featuring 50+ restaurants...",
  "ai_summary": "Dubai's biggest beachside food festival with live cooking demos and family activities",
  
  // Existing fields remain...
  
  "event_url": "https://dubaifoodfestival.com/events/la-mer-beach-2025",
  "social_media": {
    "instagram": "@dubaifoodfest",
    "facebook": "facebook.com/DubaiFoodFestival",
    "twitter": "@DubaiFoodFest",
    "tiktok": "@dubaifoodfest",
    "youtube": null,
    "whatsapp": "https://wa.me/g/DFFBeach2025",
    "telegram": null
  },
  
  "quality_metrics": {
    "extraction_confidence": 0.92,
    "data_completeness": 0.85,
    "source_reliability": "high",
    "last_verified": "2025-06-21T14:30:00",
    "extraction_method": "perplexity_search",
    "validation_warnings": ["end_date estimated based on typical event duration"]
  },
  
  // Other existing fields...
}
```

## Implementation Notes

1. Preserve the existing JSON schema but add new optional fields
2. Enhance the `create_search_and_extract_prompt()` method to include new requirements
3. Add the new search queries to `discover_events_by_categories()`
4. Implement the filter-to-query system as a separate method
5. Keep all logging patterns consistent with existing code
6. Ensure all new fields are optional to maintain backward compatibility

Please implement these enhancements while maintaining the robustness and reliability of the existing extractor.