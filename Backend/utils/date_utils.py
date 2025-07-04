"""
Intelligent Date Utilities for Event Filtering
Provides smart date range calculations and weekday/weekend detection
"""

from datetime import datetime, timedelta, time
from typing import Tuple, Dict, List, Optional
from enum import Enum
import pytz

# Dubai timezone
DUBAI_TZ = pytz.timezone('Asia/Dubai')

class DayType(Enum):
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

class DateRange(Enum):
    TODAY = "today"
    TOMORROW = "tomorrow"
    THIS_WEEK = "this_week"
    NEXT_WEEK = "next_week"
    THIS_WEEKEND = "this_weekend"
    NEXT_WEEKEND = "next_weekend"
    THIS_MONTH = "this_month"
    NEXT_MONTH = "next_month"

def get_dubai_now() -> datetime:
    """Get current time in Dubai timezone"""
    return datetime.now(DUBAI_TZ)

def get_utc_now() -> datetime:
    """Get current UTC time"""
    return datetime.utcnow()

def convert_to_dubai_time(dt: datetime) -> datetime:
    """Convert datetime to Dubai timezone"""
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        dt = pytz.utc.localize(dt)
    return dt.astimezone(DUBAI_TZ)

def convert_to_utc(dt: datetime) -> datetime:
    """Convert datetime to UTC"""
    if dt.tzinfo is None:
        # Assume Dubai time if no timezone info
        dt = DUBAI_TZ.localize(dt)
    return dt.astimezone(pytz.utc).replace(tzinfo=None)

def is_weekend_day(dt: datetime) -> bool:
    """
    Check if a date falls on weekend in Dubai context
    Weekend in Dubai: Saturday (5) and Sunday (6)
    """
    dubai_dt = convert_to_dubai_time(dt)
    return dubai_dt.weekday() in [5, 6]  # Saturday=5, Sunday=6

def is_weekday(dt: datetime) -> bool:
    """Check if a date falls on a weekday (Monday-Friday in Dubai)"""
    return not is_weekend_day(dt)

def get_day_type(dt: datetime) -> DayType:
    """Get the day type for a given datetime"""
    dubai_dt = convert_to_dubai_time(dt)
    weekday = dubai_dt.weekday()
    
    if weekday == 5:  # Saturday
        return DayType.SATURDAY
    elif weekday == 6:  # Sunday
        return DayType.SUNDAY
    elif weekday in [5, 6]:  # Weekend
        return DayType.WEEKEND
    else:  # Monday-Friday
        return DayType.WEEKDAY

def get_week_start_end(dt: datetime) -> Tuple[datetime, datetime]:
    """
    Get start and end of week for a given date
    Week starts on Monday in Dubai context (since weekend is Sat-Sun)
    """
    dubai_dt = convert_to_dubai_time(dt)
    days_since_monday = dubai_dt.weekday()  # Monday=0, so this gives days since Monday
    
    week_start = dubai_dt - timedelta(days=days_since_monday)
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    return convert_to_utc(week_start), convert_to_utc(week_end)

def get_weekend_start_end(dt: datetime) -> Tuple[datetime, datetime]:
    """
    Get start and end of weekend for a given week
    Weekend: Saturday 00:00 to Sunday 23:59
    """
    dubai_dt = convert_to_dubai_time(dt)
    
    # Find Saturday of this week
    days_since_monday = dubai_dt.weekday()  # Monday=0
    saturday_offset = (5 - days_since_monday) % 7  # Saturday=5
    if saturday_offset == 0 and dubai_dt.weekday() > 5:
        # If it's Sunday, get next Saturday
        saturday_offset = 7 - days_since_monday + 5
    
    saturday = dubai_dt + timedelta(days=saturday_offset)
    saturday_start = saturday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    sunday_end = saturday_start + timedelta(days=1, hours=23, minutes=59, seconds=59)
    
    return convert_to_utc(saturday_start), convert_to_utc(sunday_end)

def get_month_start_end(dt: datetime) -> Tuple[datetime, datetime]:
    """Get start and end of month for a given date"""
    dubai_dt = convert_to_dubai_time(dt)
    
    month_start = dubai_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Get last day of month
    if dubai_dt.month == 12:
        next_month = dubai_dt.replace(year=dubai_dt.year + 1, month=1, day=1)
    else:
        next_month = dubai_dt.replace(month=dubai_dt.month + 1, day=1)
    
    month_end = next_month - timedelta(days=1)
    month_end = month_end.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    return convert_to_utc(month_start), convert_to_utc(month_end)

def calculate_date_range(range_type: str, reference_date: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Calculate date range based on intelligent date filters
    
    Args:
        range_type: Type of date range (today, tomorrow, this_week, etc.)
        reference_date: Reference date (defaults to current Dubai time)
    
    Returns:
        Tuple of (start_date, end_date) in UTC
    """
    if reference_date is None:
        reference_date = get_dubai_now()
    else:
        reference_date = convert_to_dubai_time(reference_date)
    
    if range_type == DateRange.TODAY.value:
        start = reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = reference_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        return convert_to_utc(start), convert_to_utc(end)
    
    elif range_type == DateRange.TOMORROW.value:
        tomorrow = reference_date + timedelta(days=1)
        start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
        return convert_to_utc(start), convert_to_utc(end)
    
    elif range_type == DateRange.THIS_WEEK.value:
        return get_week_start_end(reference_date)
    
    elif range_type == DateRange.NEXT_WEEK.value:
        next_week = reference_date + timedelta(days=7)
        return get_week_start_end(next_week)
    
    elif range_type == DateRange.THIS_WEEKEND.value:
        return get_weekend_start_end(reference_date)
    
    elif range_type == DateRange.NEXT_WEEKEND.value:
        # Find next weekend
        current_weekend_start, current_weekend_end = get_weekend_start_end(reference_date)
        
        # If we're past this weekend, next weekend is next week
        if convert_to_dubai_time(get_utc_now()) > convert_to_dubai_time(current_weekend_end):
            next_week = reference_date + timedelta(days=7)
            return get_weekend_start_end(next_week)
        else:
            # If current weekend hasn't passed, next weekend is the week after
            next_weekend_date = reference_date + timedelta(days=7)
            return get_weekend_start_end(next_weekend_date)
    
    elif range_type == DateRange.THIS_MONTH.value:
        return get_month_start_end(reference_date)
    
    elif range_type == DateRange.NEXT_MONTH.value:
        if reference_date.month == 12:
            next_month = reference_date.replace(year=reference_date.year + 1, month=1)
        else:
            next_month = reference_date.replace(month=reference_date.month + 1)
        return get_month_start_end(next_month)
    
    else:
        # Default to today if unknown range
        return calculate_date_range(DateRange.TODAY.value, reference_date)

def get_available_date_filters() -> List[Dict[str, str]]:
    """Get list of available smart date filters for frontend"""
    return [
        {"value": "today", "label": "Today", "description": "Events happening today"},
        {"value": "tomorrow", "label": "Tomorrow", "description": "Events happening tomorrow"},
        {"value": "this_week", "label": "This Week", "description": "Events this week (Mon-Sun)"},
        {"value": "next_week", "label": "Next Week", "description": "Events next week"},
        {"value": "this_weekend", "label": "This Weekend", "description": "Events this weekend (Sat-Sun)"},
        {"value": "next_weekend", "label": "Next Weekend", "description": "Events next weekend"},
        {"value": "this_month", "label": "This Month", "description": "Events this month"},
        {"value": "next_month", "label": "Next Month", "description": "Events next month"},
        {"value": "weekdays", "label": "Weekdays Only", "description": "Events on Mon-Fri"},
        {"value": "weekends", "label": "Weekends Only", "description": "Events on Sat-Sun"},
    ]

def filter_events_by_day_type(events: List[Dict], day_type: str) -> List[Dict]:
    """
    Filter events by day type (weekday/weekend)
    
    Args:
        events: List of event documents
        day_type: 'weekdays' or 'weekends'
    
    Returns:
        Filtered list of events
    """
    filtered_events = []
    
    # For weekend filtering, we need to check if events occur during the weekend
    if day_type == 'weekends':
        # Get this weekend's date range
        start_date, end_date = calculate_date_range('this_weekend')
        
        for event in events:
            event_start = event.get('start_date')
            event_end = event.get('end_date', event_start)  # Use start_date if no end_date
            
            if not event_start:
                continue
            
            # Convert to datetime if string
            if isinstance(event_start, str):
                try:
                    event_start = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                except:
                    continue
                    
            if isinstance(event_end, str):
                try:
                    event_end = datetime.fromisoformat(event_end.replace('Z', '+00:00'))
                except:
                    event_end = event_start
            
            # Check if event overlaps with weekend period
            if (event_start <= end_date and event_end >= start_date):
                filtered_events.append(event)
                
    elif day_type == 'weekdays':
        # For weekdays, keep the original logic (events starting on weekdays)
        for event in events:
            start_date = event.get('start_date')
            if not start_date:
                continue
                
            if isinstance(start_date, str):
                try:
                    start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                except:
                    continue
            
            if is_weekday(start_date):
                filtered_events.append(event)
    
    return filtered_events

def get_events_date_filter_query(date_filter: str) -> Dict:
    """
    Generate MongoDB query for date filtering
    
    Args:
        date_filter: Date filter type (today, tomorrow, this_week, etc.)
    
    Returns:
        MongoDB query dict for date filtering
    """
    if date_filter in ['weekdays', 'weekends']:
        # These require post-processing, so return empty query
        return {}
    
    try:
        start_date, end_date = calculate_date_range(date_filter)
        return {
            "$and": [
                {"start_date": {"$gte": start_date}},
                {"start_date": {"$lte": end_date}}
            ]
        }
    except:
        return {}

def format_date_for_display(dt: datetime, include_time: bool = True) -> str:
    """Format datetime for display in Dubai timezone"""
    dubai_dt = convert_to_dubai_time(dt)
    
    if include_time:
        return dubai_dt.strftime("%Y-%m-%d %I:%M %p")
    else:
        return dubai_dt.strftime("%Y-%m-%d")

def get_relative_date_description(dt: datetime) -> str:
    """Get relative description for a date (Today, Tomorrow, etc.)"""
    dubai_now = get_dubai_now()
    dubai_dt = convert_to_dubai_time(dt)
    
    days_diff = (dubai_dt.date() - dubai_now.date()).days
    
    if days_diff == 0:
        return "Today"
    elif days_diff == 1:
        return "Tomorrow"
    elif days_diff == -1:
        return "Yesterday"
    elif 1 < days_diff <= 7:
        return dubai_dt.strftime("%A")  # Day name
    elif days_diff > 7:
        return dubai_dt.strftime("%B %d")  # Month Day
    else:
        return dubai_dt.strftime("%B %d, %Y")  # Full date

def debug_date_info(dt: datetime) -> Dict:
    """Get debug information about a datetime for troubleshooting"""
    dubai_dt = convert_to_dubai_time(dt)
    utc_dt = convert_to_utc(dt)
    
    return {
        "original": str(dt),
        "dubai_time": str(dubai_dt),
        "utc_time": str(utc_dt),
        "weekday": dubai_dt.weekday(),
        "weekday_name": dubai_dt.strftime("%A"),
        "is_weekend": is_weekend_day(dt),
        "day_type": get_day_type(dt).value,
        "relative_description": get_relative_date_description(dt)
    }