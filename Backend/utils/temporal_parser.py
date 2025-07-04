"""
Temporal Expression Parser for Natural Language Date Queries
Integrates with date_utils for intelligent date range detection
"""

import re
from typing import Optional, Dict, Tuple, List
from datetime import datetime, timedelta
from utils.date_utils import (
    calculate_date_range, get_dubai_now, 
    is_weekend_day, is_weekday, get_available_date_filters
)

class TemporalParser:
    """Parse natural language temporal expressions in search queries"""
    
    def __init__(self):
        # Define temporal patterns with their corresponding date_filter mappings
        self.temporal_patterns = {
            # Immediate time references
            r'\b(today|tonight)\b': 'today',
            r'\b(tomorrow)\b': 'tomorrow',
            
            # Week references
            r'\b(this\s+week)\b': 'this_week',
            r'\b(next\s+week)\b': 'next_week',
            r'\b(coming\s+week)\b': 'next_week',
            
            # Weekend references
            r'\b(this\s+weekend)\b': 'this_weekend',
            r'\b(next\s+weekend)\b': 'next_weekend',
            r'\b(coming\s+weekend)\b': 'next_weekend',
            r'\b(this\s+saturday)\b': 'this_weekend',
            r'\b(this\s+sunday)\b': 'this_weekend',
            r'\b(weekends?)\b': 'weekends',
            
            # Weekday references
            r'\b(weekdays?)\b': 'weekdays',
            r'\b(during\s+the\s+week)\b': 'weekdays',
            r'\b(monday\s+to\s+friday)\b': 'weekdays',
            r'\b(mon-fri)\b': 'weekdays',
            
            # Month references
            r'\b(this\s+month)\b': 'this_month',
            r'\b(next\s+month)\b': 'next_month',
            r'\b(coming\s+month)\b': 'next_month',
            
            # Specific day patterns
            r'\b(next\s+(?:monday|tuesday|wednesday|thursday|friday))\b': 'next_week',
            r'\b(next\s+(?:saturday|sunday))\b': 'next_weekend',
            r'\b(this\s+(?:monday|tuesday|wednesday|thursday|friday))\b': 'this_week',
            
            # Relative patterns
            r'\b(in\s+a\s+few\s+days)\b': 'this_week',
            r'\b(later\s+this\s+week)\b': 'this_week',
            r'\b(early\s+next\s+week)\b': 'next_week',
        }
        
        # Keywords that suggest family-friendly filtering
        self.family_keywords = {
            'family', 'families', 'kids', 'children', 'child', 'toddler', 'toddlers',
            'baby', 'babies', 'infant', 'infants', 'all ages', 'all-ages',
            'family-friendly', 'kid-friendly', 'child-friendly'
        }
        
        # Keywords that suggest specific age groups
        self.age_keywords = {
            'baby': 'toddlers',
            'babies': 'toddlers', 
            'infant': 'toddlers',
            'infants': 'toddlers',
            'toddler': 'toddlers',
            'toddlers': 'toddlers',
            'kids': 'kids',
            'children': 'kids',
            'child': 'kids',
            'teen': 'teenagers',
            'teens': 'teenagers',
            'teenager': 'teenagers',
            'teenagers': 'teenagers',
            'adult': 'adults',
            'adults': 'adults',
            'seniors': 'seniors',
            'elderly': 'seniors'
        }
        
        # Location keywords for Dubai areas
        self.location_keywords = {
            'downtown', 'marina', 'jbr', 'jumeirah', 'deira', 'bur dubai',
            'business bay', 'sheikh zayed road', 'mall of emirates', 'dubai mall',
            'city walk', 'la mer', 'kite beach', 'jumeirah beach', 'palm jumeirah',
            'dubai hills', 'motor city', 'sports city', 'studio city',
            'international city', 'dragon mart', 'al seef', 'old dubai',
            'creek', 'festival city', 'silicon oasis', 'academic city'
        }
    
    def parse_temporal_expression(self, query: str) -> Dict:
        """
        Parse temporal expressions from natural language query
        
        Args:
            query: Natural language search query
            
        Returns:
            Dict containing parsed temporal information
        """
        query_lower = query.lower()
        
        # Find temporal expressions
        date_filter = None
        time_period = None
        confidence = 0.0
        
        for pattern, filter_value in self.temporal_patterns.items():
            if re.search(pattern, query_lower, re.IGNORECASE):
                date_filter = filter_value
                time_period = filter_value
                confidence = 0.9
                break
        
        # Detect family-friendly intent
        family_friendly = None
        age_group = None
        
        # Check for family keywords
        query_words = set(query_lower.split())
        if query_words & self.family_keywords:
            family_friendly = True
            confidence = max(confidence, 0.8)
        
        # Check for age group keywords
        for word in query_words:
            if word in self.age_keywords:
                age_group = self.age_keywords[word]
                if age_group in ['toddlers', 'kids']:
                    family_friendly = True
                confidence = max(confidence, 0.8)
                break
        
        # Detect location preferences
        location_preferences = []
        for word in query_words:
            if word in self.location_keywords:
                location_preferences.append(word.title())
                confidence = max(confidence, 0.7)
        
        # Calculate date ranges if temporal expression found
        date_from = None
        date_to = None
        
        if date_filter and date_filter not in ['weekdays', 'weekends']:
            try:
                start_date, end_date = calculate_date_range(date_filter)
                date_from = start_date.isoformat() if start_date else None
                date_to = end_date.isoformat() if end_date else None
            except Exception:
                pass
        
        return {
            'date_filter': date_filter,
            'time_period': time_period,
            'date_from': date_from,
            'date_to': date_to,
            'family_friendly': family_friendly,
            'age_group': age_group,
            'location_preferences': location_preferences,
            'confidence': confidence
        }
    
    def enhance_query_analysis(self, query: str, ai_analysis: Dict) -> Dict:
        """
        Enhance AI analysis with temporal parsing results
        
        Args:
            query: Original search query
            ai_analysis: Analysis from OpenAI service
            
        Returns:
            Enhanced analysis combining AI and temporal parsing
        """
        temporal_data = self.parse_temporal_expression(query)
        
        # Merge temporal data with AI analysis, giving priority to temporal parser for dates
        enhanced = ai_analysis.copy()
        
        # Override date information if temporal parser found something
        if temporal_data['date_filter']:
            enhanced['date_filter'] = temporal_data['date_filter']
            enhanced['time_period'] = temporal_data['time_period']
            
            # Only override date_from/date_to if temporal parser has specific dates
            if temporal_data['date_from']:
                enhanced['date_from'] = temporal_data['date_from']
            if temporal_data['date_to']:
                enhanced['date_to'] = temporal_data['date_to']
        
        # Enhance family-friendly detection
        if temporal_data['family_friendly'] is not None:
            enhanced['family_friendly'] = temporal_data['family_friendly']
        
        # Enhance age group detection
        if temporal_data['age_group']:
            enhanced['age_group'] = temporal_data['age_group']
        
        # Merge location preferences
        if temporal_data['location_preferences']:
            existing_locations = enhanced.get('location_preferences', [])
            all_locations = list(set(existing_locations + temporal_data['location_preferences']))
            enhanced['location_preferences'] = all_locations
        
        # Update confidence based on temporal parsing
        if temporal_data['confidence'] > 0:
            enhanced['confidence'] = max(enhanced.get('confidence', 0), temporal_data['confidence'])
        
        return enhanced
    
    def get_smart_date_query(self, date_filter: str) -> Dict:
        """
        Get MongoDB query for smart date filtering
        
        Args:
            date_filter: Date filter type (today, this_weekend, weekdays, etc.)
            
        Returns:
            MongoDB query dict
        """
        if not date_filter:
            return {}
        
        if date_filter in ['weekdays', 'weekends']:
            # These require post-processing, return empty query
            return {}
        
        try:
            start_date, end_date = calculate_date_range(date_filter)
            return {
                "$and": [
                    {"start_date": {"$gte": start_date}},
                    {"start_date": {"$lte": end_date}}
                ]
            }
        except Exception:
            return {}
    
    def get_example_queries(self) -> List[Dict[str, str]]:
        """Get example queries that demonstrate temporal parsing capabilities"""
        return [
            {"query": "family events this weekend", "description": "Shows Saturday-Sunday family activities"},
            {"query": "kids activities next week", "description": "Shows children's events for upcoming Monday-Sunday"},
            {"query": "dinner places tomorrow", "description": "Shows dining options for tomorrow"},
            {"query": "outdoor activities weekdays", "description": "Shows Monday-Friday outdoor events"},
            {"query": "concerts this coming Saturday", "description": "Shows Saturday concerts"},
            {"query": "free events this month", "description": "Shows free events for current month"},
            {"query": "cultural events next weekend", "description": "Shows cultural activities for next Saturday-Sunday"},
            {"query": "toddler activities in marina", "description": "Shows toddler-friendly events in Dubai Marina"}
        ]

# Global instance for easy import
temporal_parser = TemporalParser()