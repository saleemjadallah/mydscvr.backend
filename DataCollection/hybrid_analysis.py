#!/usr/bin/env python3
"""
Hybrid Collection Analysis Tool
Analyzes the effectiveness of hybrid collection (Perplexity + Firecrawl)
including deduplication statistics and source analysis
"""

import os
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
from pymongo import MongoClient
from loguru import logger
import re

# Add backend path for deduplication
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Backend'))

class HybridCollectionAnalyzer:
    """
    Comprehensive analysis of hybrid collection results
    """
    
    def __init__(self):
        # MongoDB connection
        self.mongodb_uri = os.getenv('Mongo_URI')
        self.database_name = os.getenv('MONGO_DB_NAME', 'DXB')
        
        if not self.mongodb_uri:
            raise ValueError("MongoDB URI not found")
        
        try:
            self.client = MongoClient(
                self.mongodb_uri,
                serverSelectionTimeoutMS=5000,
                tlsInsecure=True
            )
            
            self.db = self.client[self.database_name]
            self.events_collection = self.db['events']
            
            logger.info("✅ Connected to MongoDB for hybrid analysis")
            
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise
    
    def analyze_hybrid_collection(self) -> Dict[str, Any]:
        """
        Comprehensive analysis of hybrid collection results
        """
        logger.info("🔍 Starting hybrid collection analysis...")
        
        # Get all events
        all_events = list(self.events_collection.find({}))
        total_events = len(all_events)
        
        logger.info(f"📊 Total events in database: {total_events}")
        
        if total_events == 0:
            logger.warning("⚠️ No events found in database")
            return {}
        
        # Analyze by extraction source
        source_stats = self._analyze_by_source(all_events)
        
        # Analyze categories and family scores
        category_stats = self._analyze_categories(all_events)
        
        # Analyze venues and locations
        venue_stats = self._analyze_venues(all_events)
        
        # Analyze duplicates and similarity
        duplicate_stats = self._analyze_duplicates(all_events)
        
        # Analyze temporal distribution
        temporal_stats = self._analyze_temporal_distribution(all_events)
        
        # Quality analysis
        quality_stats = self._analyze_quality_metrics(all_events)
        
        # Compile comprehensive report
        analysis_report = {
            "analysis_timestamp": datetime.now().isoformat(),
            "total_events": total_events,
            "source_analysis": source_stats,
            "category_analysis": category_stats,
            "venue_analysis": venue_stats,
            "duplicate_analysis": duplicate_stats,
            "temporal_analysis": temporal_stats,
            "quality_analysis": quality_stats
        }
        
        return analysis_report
    
    def _analyze_by_source(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze events by extraction source"""
        logger.info("📡 Analyzing events by extraction source...")
        
        source_counts = Counter()
        source_details = defaultdict(list)
        
        for event in events:
            # Check multiple possible source fields
            source = event.get('source', event.get('extraction_source', 'unknown'))
            extraction_method = event.get('quality_metrics', {}).get('extraction_method', '')
            
            if 'firecrawl' in source.lower() or 'firecrawl' in extraction_method.lower():
                source_type = 'firecrawl'
            elif 'perplexity' in source.lower() or 'perplexity' in extraction_method.lower():
                source_type = 'perplexity'
            else:
                source_type = 'unknown'
            
            source_counts[source_type] += 1
            # Get venue name from nested venue object
            venue_name = 'Unknown'
            if event.get('venue') and isinstance(event['venue'], dict):
                venue_name = event['venue'].get('name', 'Unknown')
            elif event.get('venue_name'):
                venue_name = event.get('venue_name')
            
            source_details[source_type].append({
                'title': event.get('title', 'No title')[:50],
                'venue': venue_name,
                'category': event.get('primary_category', 'Unknown'),
                'family_score': event.get('family_score', 0)
            })
        
        return {
            "source_counts": dict(source_counts),
            "source_breakdown": dict(source_details),
            "perplexity_percentage": round((source_counts['perplexity'] / len(events)) * 100, 1),
            "firecrawl_percentage": round((source_counts['firecrawl'] / len(events)) * 100, 1)
        }
    
    def _analyze_categories(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze event categories and family friendliness"""
        logger.info("🏷️ Analyzing event categories...")
        
        categories = Counter()
        family_scores = []
        family_by_category = defaultdict(list)
        
        for event in events:
            category = event.get('primary_category', 'unknown')
            categories[category] += 1
            
            family_score = event.get('family_score', 0)
            family_scores.append(family_score)
            family_by_category[category].append(family_score)
        
        # Calculate family score statistics by category
        category_family_stats = {}
        for category, scores in family_by_category.items():
            if scores:
                category_family_stats[category] = {
                    'count': len(scores),
                    'avg_family_score': round(sum(scores) / len(scores), 1),
                    'family_friendly_count': len([s for s in scores if s >= 70])
                }
        
        return {
            "category_distribution": dict(categories),
            "avg_family_score": round(sum(family_scores) / len(family_scores), 1) if family_scores else 0,
            "family_friendly_events": len([s for s in family_scores if s >= 70]),
            "family_friendly_percentage": round((len([s for s in family_scores if s >= 70]) / len(events)) * 100, 1),
            "category_family_breakdown": category_family_stats
        }
    
    def _analyze_venues(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze venue distribution and popular locations"""
        logger.info("🏢 Analyzing venues and locations...")
        
        venues = Counter()
        areas = Counter()
        
        for event in events:
            # Get venue and area from nested venue object
            venue = 'Unknown'
            area = 'Unknown'
            
            if event.get('venue') and isinstance(event['venue'], dict):
                venue = event['venue'].get('name', 'Unknown')
                area = event['venue'].get('area', 'Unknown')
            elif event.get('venue_name'):
                venue = event.get('venue_name')
                area = event.get('area', 'Unknown')
            
            if venue and venue != 'Unknown':
                venues[venue] += 1
            if area and area != 'Unknown':
                areas[area] += 1
        
        return {
            "total_unique_venues": len(venues),
            "total_unique_areas": len(areas),
            "top_venues": dict(venues.most_common(10)),
            "top_areas": dict(areas.most_common(10)),
            "events_with_venue_info": len([e for e in events if (e.get('venue') and isinstance(e['venue'], dict) and e['venue'].get('name', 'Unknown') != 'Unknown') or (e.get('venue_name') and e.get('venue_name') != 'Unknown')])
        }
    
    def _analyze_duplicates(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze potential duplicates using title similarity"""
        logger.info("🔍 Analyzing potential duplicates...")
        
        # Group events by similar titles
        title_groups = defaultdict(list)
        potential_duplicates = []
        
        for i, event in enumerate(events):
            title = event.get('title', '').lower().strip()
            if not title:
                continue
            
            # Normalize title for comparison
            normalized_title = re.sub(r'[^\w\s]', '', title)
            normalized_title = re.sub(r'\s+', ' ', normalized_title)
            
            # Look for similar titles
            found_group = False
            for group_title, group_events in title_groups.items():
                if self._titles_similar(normalized_title, group_title):
                    group_events.append((i, event))
                    found_group = True
                    break
            
            if not found_group:
                title_groups[normalized_title].append((i, event))
        
        # Find groups with multiple events (potential duplicates)
        for title, event_group in title_groups.items():
            if len(event_group) > 1:
                potential_duplicates.append({
                    'common_title': title,
                    'count': len(event_group),
                    'events': [
                        {
                            'title': e[1].get('title', 'No title'),
                            'venue': e[1].get('venue', {}).get('name', 'Unknown') if isinstance(e[1].get('venue'), dict) else e[1].get('venue_name', 'Unknown'),
                            'source': e[1].get('source', e[1].get('extraction_source', 'Unknown')),
                            'start_date': e[1].get('start_date', 'Unknown')
                        }
                        for e in event_group
                    ]
                })
        
        return {
            "total_potential_duplicate_groups": len(potential_duplicates),
            "total_events_in_duplicate_groups": sum(group['count'] for group in potential_duplicates),
            "duplicate_groups": potential_duplicates[:10],  # Top 10 for analysis
            "unique_events_estimate": len(events) - sum(group['count'] - 1 for group in potential_duplicates)
        }
    
    def _titles_similar(self, title1: str, title2: str, threshold: float = 0.8) -> bool:
        """Check if two titles are similar enough to be potential duplicates"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, title1, title2).ratio() >= threshold
    
    def _analyze_temporal_distribution(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze temporal distribution of events"""
        logger.info("📅 Analyzing temporal distribution...")
        
        months = Counter()
        future_events = 0
        events_with_dates = 0
        
        for event in events:
            start_date_str = event.get('start_date')
            if start_date_str:
                try:
                    if isinstance(start_date_str, str):
                        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                    else:
                        start_date = start_date_str
                    
                    month_key = start_date.strftime('%Y-%m')
                    months[month_key] += 1
                    events_with_dates += 1
                    
                    if start_date > datetime.now(start_date.tzinfo or timezone.utc):
                        future_events += 1
                        
                except Exception:
                    continue
        
        return {
            "events_with_valid_dates": events_with_dates,
            "future_events": future_events,
            "monthly_distribution": dict(months.most_common(12)),
            "date_coverage_percentage": round((events_with_dates / len(events)) * 100, 1)
        }
    
    def _analyze_quality_metrics(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze data quality metrics"""
        logger.info("⭐ Analyzing data quality metrics...")
        
        quality_metrics = {
            'events_with_title': 0,
            'events_with_description': 0,
            'events_with_venue': 0,
            'events_with_dates': 0,
            'events_with_price': 0,
            'events_with_family_score': 0,
            'events_with_category': 0,
            'complete_events': 0
        }
        
        for event in events:
            if event.get('title'):
                quality_metrics['events_with_title'] += 1
            if event.get('description'):
                quality_metrics['events_with_description'] += 1
            # Check for venue info in nested venue object or direct field
            has_venue = False
            if event.get('venue') and isinstance(event['venue'], dict) and event['venue'].get('name'):
                has_venue = True
            elif event.get('venue_name'):
                has_venue = True
                
            if has_venue:
                quality_metrics['events_with_venue'] += 1
            if event.get('start_date'):
                quality_metrics['events_with_dates'] += 1
            if event.get('min_price') is not None or event.get('max_price') is not None:
                quality_metrics['events_with_price'] += 1
            if event.get('family_score') is not None:
                quality_metrics['events_with_family_score'] += 1
            if event.get('primary_category'):
                quality_metrics['events_with_category'] += 1
            
            # Complete event has title, description, venue, date, category
            venue_exists = (event.get('venue') and isinstance(event['venue'], dict) and event['venue'].get('name')) or event.get('venue_name')
            if all([
                event.get('title'),
                event.get('description'),
                venue_exists,
                event.get('start_date'),
                event.get('primary_category')
            ]):
                quality_metrics['complete_events'] += 1
        
        # Convert to percentages
        total = len(events)
        quality_percentages = {
            key: round((value / total) * 100, 1)
            for key, value in quality_metrics.items()
        }
        
        return {
            "raw_counts": quality_metrics,
            "percentages": quality_percentages,
            "data_completeness_score": round(sum(quality_percentages.values()) / len(quality_percentages), 1)
        }
    
    def print_analysis_report(self, analysis: Dict[str, Any]):
        """Print a comprehensive analysis report"""
        logger.info("📊 HYBRID COLLECTION ANALYSIS REPORT")
        logger.info("=" * 60)
        
        # Overall stats
        logger.info(f"🎯 Total Events: {analysis['total_events']}")
        logger.info(f"📅 Analysis Time: {analysis['analysis_timestamp']}")
        logger.info("")
        
        # Source analysis
        source = analysis['source_analysis']
        logger.info("📡 SOURCE ANALYSIS:")
        logger.info(f"   • Perplexity Events: {source['source_counts'].get('perplexity', 0)} ({source['perplexity_percentage']}%)")
        logger.info(f"   • Firecrawl Events: {source['source_counts'].get('firecrawl', 0)} ({source['firecrawl_percentage']}%)")
        logger.info("")
        
        # Category analysis
        categories = analysis['category_analysis']
        logger.info("🏷️ CATEGORY ANALYSIS:")
        logger.info(f"   • Average Family Score: {categories['avg_family_score']}/100")
        logger.info(f"   • Family-Friendly Events: {categories['family_friendly_events']} ({categories['family_friendly_percentage']}%)")
        logger.info("   • Top Categories:")
        for cat, count in list(categories['category_distribution'].items())[:5]:
            percentage = round((count / analysis['total_events']) * 100, 1)
            logger.info(f"     - {cat}: {count} ({percentage}%)")
        logger.info("")
        
        # Venue analysis
        venues = analysis['venue_analysis']
        logger.info("🏢 VENUE ANALYSIS:")
        logger.info(f"   • Unique Venues: {venues['total_unique_venues']}")
        logger.info(f"   • Unique Areas: {venues['total_unique_areas']}")
        logger.info(f"   • Events with Venue Info: {venues['events_with_venue_info']}")
        logger.info("   • Top Areas:")
        for area, count in list(venues['top_areas'].items())[:5]:
            logger.info(f"     - {area}: {count} events")
        logger.info("")
        
        # Duplicate analysis
        duplicates = analysis['duplicate_analysis']
        logger.info("🔍 DUPLICATE ANALYSIS:")
        logger.info(f"   • Potential Duplicate Groups: {duplicates['total_potential_duplicate_groups']}")
        logger.info(f"   • Events in Duplicate Groups: {duplicates['total_events_in_duplicate_groups']}")
        logger.info(f"   • Estimated Unique Events: {duplicates['unique_events_estimate']}")
        if duplicates['duplicate_groups']:
            logger.info("   • Top Duplicate Groups:")
            for group in duplicates['duplicate_groups'][:3]:
                logger.info(f"     - '{group['common_title'][:40]}...': {group['count']} similar events")
        logger.info("")
        
        # Quality analysis
        quality = analysis['quality_analysis']
        logger.info("⭐ DATA QUALITY ANALYSIS:")
        logger.info(f"   • Data Completeness Score: {quality['data_completeness_score']}/100")
        logger.info(f"   • Complete Events: {quality['raw_counts']['complete_events']} ({quality['percentages']['complete_events']}%)")
        logger.info("   • Field Coverage:")
        logger.info(f"     - Titles: {quality['percentages']['events_with_title']}%")
        logger.info(f"     - Descriptions: {quality['percentages']['events_with_description']}%")
        logger.info(f"     - Venues: {quality['percentages']['events_with_venue']}%")
        logger.info(f"     - Dates: {quality['percentages']['events_with_dates']}%")
        logger.info(f"     - Categories: {quality['percentages']['events_with_category']}%")
        logger.info("")
        
        # Temporal analysis
        temporal = analysis['temporal_analysis']
        logger.info("📅 TEMPORAL ANALYSIS:")
        logger.info(f"   • Future Events: {temporal['future_events']}")
        logger.info(f"   • Date Coverage: {temporal['date_coverage_percentage']}%")
        logger.info("")
        
        logger.info("🎉 HYBRID ANALYSIS COMPLETE!")
        logger.info("=" * 60)
    
    def close(self):
        """Close MongoDB connection"""
        if hasattr(self, 'client'):
            self.client.close()
            logger.info("🔌 MongoDB connection closed")

def main():
    """Run hybrid collection analysis"""
    try:
        # Load environment
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'Mongo.env'))
        
        analyzer = HybridCollectionAnalyzer()
        analysis = analyzer.analyze_hybrid_collection()
        
        if analysis:
            analyzer.print_analysis_report(analysis)
            
            # Save detailed analysis to file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"hybrid_analysis_{timestamp}.json"
            
            with open(filename, 'w') as f:
                json.dump(analysis, f, indent=2, default=str)
            
            logger.info(f"💾 Detailed analysis saved to: {filename}")
        
        analyzer.close()
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        raise

if __name__ == "__main__":
    main()