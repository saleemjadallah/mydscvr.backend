"""
Lifecycle Management Task API Endpoints

Replaces Celery task queue with direct API endpoints for lifecycle management tasks.
These endpoints can be called manually or via cron jobs.
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
import logging
from lifecycle_management.tasks import (
    create_daily_hidden_gem,
    cleanup_expired_gems,
    daily_storage_health_check,
    daily_source_based_cleanup,
    weekly_retention_report
)

router = APIRouter(
    prefix="/lifecycle/tasks",
    tags=["lifecycle-tasks"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)

@router.post("/create-hidden-gem")
async def trigger_create_hidden_gem():
    """
    Create daily hidden gem
    
    Previously: Celery task scheduled for 1 AM UAE
    Now: Manual trigger or cron job at 5 AM UAE (1 AM UTC) - No conflicts!
    """
    try:
        result = await create_daily_hidden_gem()
        return {
            "task": "create_daily_hidden_gem",
            "triggered_at": datetime.now().isoformat(),
            "result": result
        }
    except Exception as e:
        logger.error(f"Error triggering hidden gem creation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup-gems")
async def trigger_cleanup_gems():
    """
    Clean up expired hidden gems
    
    Previously: Celery task scheduled for Sunday 1:30 AM UAE
    Now: Manual trigger or weekly cron job
    """
    try:
        result = await cleanup_expired_gems()
        return {
            "task": "cleanup_expired_gems",
            "triggered_at": datetime.now().isoformat(),
            "result": result
        }
    except Exception as e:
        logger.error(f"Error triggering gem cleanup: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/health-check")
async def trigger_health_check():
    """
    Perform daily storage health check
    
    Previously: Celery task scheduled for 2 AM UAE - CONFLICTED with datacollection!
    Now: Manual trigger or cron job at 8 AM UAE (4 AM UTC) - Safe timing!
    """
    try:
        result = await daily_storage_health_check()
        return {
            "task": "daily_storage_health_check",
            "triggered_at": datetime.now().isoformat(),
            "result": result
        }
    except Exception as e:
        logger.error(f"Error triggering health check: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/daily-cleanup")
async def trigger_daily_cleanup():
    """
    Perform daily source-based cleanup
    
    Previously: Celery task scheduled for 3 AM UAE - CONFLICTED with datacollection!
    Now: Manual trigger or cron job at 6 AM UAE (2 AM UTC) - Safe timing!
    """
    try:
        result = await daily_source_based_cleanup()
        return {
            "task": "daily_source_based_cleanup",
            "triggered_at": datetime.now().isoformat(),
            "result": result
        }
    except Exception as e:
        logger.error(f"Error triggering daily cleanup: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/weekly-report")
async def trigger_weekly_report():
    """
    Generate weekly retention report
    
    Previously: Celery task scheduled for Monday 4 AM UAE
    Now: Manual trigger or weekly cron job at Monday 10 AM UAE (6 AM UTC)
    """
    try:
        result = await weekly_retention_report()
        return {
            "task": "weekly_retention_report",
            "triggered_at": datetime.now().isoformat(),
            "result": result
        }
    except Exception as e:
        logger.error(f"Error triggering weekly report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refresh-mydscvr-choice")
async def trigger_refresh_mydscvr_choice():
    """
    Refresh MyDscvr's Choice daily featured event
    
    Previously: No automated task
    Now: Manual trigger or cron job at 7 AM UAE (3 AM UTC) - Daily refresh
    """
    try:
        from routers.mydscvr_choice import MyDscvrChoiceService
        from database import get_mongodb_client
        
        mongodb = await get_mongodb_client()
        service = MyDscvrChoiceService(mongodb)
        
        logger.info("🎯 Triggering MyDscvr's Choice daily refresh...")
        selected_event = await service.select_daily_event()
        
        if selected_event:
            saved_choice = await service.save_daily_choice(selected_event)
            return {
                "task": "refresh_mydscvr_choice",
                "triggered_at": datetime.now().isoformat(),
                "result": {
                    "success": True,
                    "event_title": saved_choice["event_data"]["title"],
                    "event_id": saved_choice["event_id"],
                    "total_score": saved_choice["total_score"],
                    "is_firecrawl": saved_choice["is_firecrawl"]
                }
            }
        else:
            return {
                "task": "refresh_mydscvr_choice",
                "triggered_at": datetime.now().isoformat(),
                "result": {
                    "success": False,
                    "message": "No suitable events available for MyDscvr's Choice"
                }
            }
    except Exception as e:
        logger.error(f"Error triggering MyDscvr's Choice refresh: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_task_status():
    """
    Get status of lifecycle management system
    
    Shows when tasks were last run and their results
    """
    try:
        from lifecycle_management.tasks import get_mongodb_client
        mongodb = get_mongodb_client()
        
        # Get last health check
        last_health = await mongodb.storage_health.find_one(
            {}, sort=[("checked_at", -1)]
        )
        
        # Get last hidden gem
        last_gem = await mongodb.hidden_gems.find_one(
            {"is_active": True}, sort=[("created_at", -1)]
        )
        
        # Get last weekly report
        last_report = await mongodb.weekly_reports.find_one(
            {}, sort=[("generated_at", -1)]
        )
        
        # Get last MyDscvr's Choice
        last_choice = await mongodb.mydscvr_daily_choice.find_one(
            {}, sort=[("created_at", -1)]
        )
        
        return {
            "system_status": "operational",
            "checked_at": datetime.now().isoformat(),
            "last_health_check": last_health.get("checked_at").isoformat() if last_health else None,
            "last_hidden_gem": last_gem.get("created_at").isoformat() if last_gem else None,
            "last_weekly_report": last_report.get("generated_at").isoformat() if last_report else None,
            "last_mydscvr_choice": last_choice.get("created_at").isoformat() if last_choice else None,
            "notes": "Celery removed - using direct API calls and cron jobs"
        }
        
    except Exception as e:
        logger.error(f"Error getting task status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))