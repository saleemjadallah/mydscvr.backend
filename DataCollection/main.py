#!/usr/bin/env python3
"""
Dubai Events Data Collection - Main Entry Point
Perplexity AI-based event discovery and extraction system

This replaces the old Firecrawl-based system with a simpler, more efficient approach.
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional
from loguru import logger
import argparse

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from enhanced_collection import collect_and_store_events
from config.perplexity_settings import get_settings

def setup_logging():
    """Setup enhanced logging for the main entry point"""
    logger.remove()
    
    # Console handler with colors
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
        colorize=True
    )
    
    # File handler
    log_file = Path("logs/main.log")
    log_file.parent.mkdir(exist_ok=True)
    
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days"
    )

async def run_health_check():
    """Run basic health check"""
    logger.info("🏥 Starting system health check...")
    
    try:
        settings = get_settings()
        
        # Check API keys
        checks = {
            'perplexity_api': bool(settings.PERPLEXITY_API_KEY),
            'mongodb_uri': bool(settings.MONGO_URI),
            'firecrawl_api': bool(settings.FIRECRAWL_API_KEY) if hasattr(settings, 'FIRECRAWL_API_KEY') else False
        }
        
        print(f"\n{'='*60}")
        print(f"🏥 SYSTEM HEALTH REPORT")
        print(f"{'='*60}")
        
        all_healthy = True
        for check, status in checks.items():
            emoji = "✅" if status else "❌"
            print(f"  {emoji} {check.replace('_', ' ').title()}: {'OK' if status else 'MISSING'}")
            if not status:
                all_healthy = False
        
        print(f"\nOverall Status: {'HEALTHY' if all_healthy else 'ISSUES FOUND'}")
        print(f"{'='*60}\n")
        
        return all_healthy
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False

async def run_data_collection(mode: str = "comprehensive", enable_firecrawl: bool = False):
    """Run data collection using enhanced_collection.py"""
    
    # Health check first
    if not await run_health_check():
        logger.error("❌ Health check failed. Please fix issues before running data collection.")
        return False
    
    logger.info(f"🚀 Starting {mode} data collection...")
    
    # Set environment variable for Firecrawl if requested
    if enable_firecrawl:
        import os
        os.environ['ENABLE_FIRECRAWL_SUPPLEMENT'] = 'true'
    
    try:
        result = await collect_and_store_events()
        success = result > 0
        
        if success:
            logger.success(f"✅ Data collection completed successfully!")
            logger.info(f"📊 Total events collected: {result}")
        else:
            logger.warning("⚠️ No events were collected")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Data collection failed: {e}")
        return False

async def run_status_check():
    """Run status check and show database statistics"""
    logger.info("📊 Checking current database status...")
    
    try:
        from perplexity_storage import PerplexityEventsStorage
        storage = PerplexityEventsStorage()
        
        # Get basic collection stats
        total_events = storage.get_total_events_count()
        
        print(f"\n{'='*60}")
        print(f"📊 DATABASE STATUS")
        print(f"{'='*60}")
        print(f"Total Events: {total_events}")
        print(f"Connection: {'OK' if storage else 'FAILED'}")
        print(f"{'='*60}\n")
        
        storage.close()
        
    except Exception as e:
        logger.error(f"Failed to get database status: {e}")
        print(f"\n❌ Database status check failed: {e}\n")

def main():
    """Main entry point with command line interface"""
    setup_logging()
    
    parser = argparse.ArgumentParser(
        description="Dubai Events Data Collection - Perplexity AI System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py health                     # Run health check only
  python main.py status                     # Show database status
  python main.py collect --mode test        # Test collection (few events)
  python main.py collect --mode quick       # Quick collection (family + entertainment)
  python main.py collect --mode comprehensive # Full collection (all categories)
  python main.py collect --mode targeted --categories family cultural entertainment
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Health command
    health_parser = subparsers.add_parser('health', help='Run system health check')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show database status')
    
    # Collect command
    collect_parser = subparsers.add_parser('collect', help='Run data collection')
    collect_parser.add_argument(
        '--mode', 
        choices=['test', 'quick', 'targeted', 'comprehensive'],
        default='comprehensive',
        help='Collection mode (default: comprehensive)'
    )
    collect_parser.add_argument(
        '--categories',
        nargs='+',
        help='Specific categories for targeted mode'
    )
    collect_parser.add_argument(
        '--enable-firecrawl',
        action='store_true',
        help='Enable Firecrawl MCP supplement (overrides environment setting)'
    )
    collect_parser.add_argument(
        '--firecrawl-only',
        action='store_true',
        help='Run Firecrawl extraction only (testing)'
    )
    collect_parser.add_argument(
        '--use-enhanced-collection',
        action='store_true',
        help='Use enhanced_collection.py instead of pipeline (for hybrid extraction)'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    logger.info("🌟 Dubai Events Data Collection - Perplexity AI System")
    logger.info("📍 Simplified, efficient event discovery for Dubai")
    
    try:
        if args.command == 'health':
            success = asyncio.run(run_health_check())
            sys.exit(0 if success else 1)
            
        elif args.command == 'status':
            asyncio.run(run_status_check())
            
        elif args.command == 'collect':
            # Handle Firecrawl flags
            if args.enable_firecrawl:
                import os
                os.environ['ENABLE_FIRECRAWL_SUPPLEMENT'] = 'true'
            
            if args.firecrawl_only:
                logger.info("🔥 Running Firecrawl-only extraction for testing")
                # For Firecrawl-only, we'll create a simpler version
                from firecrawl_mcp_extractor import FirecrawlMCPExtractor
                
                async def firecrawl_only():
                    extractor = FirecrawlMCPExtractor()
                    results = await extractor.extract_all_sources({'platinumlist': 5, 'timeout': 3, 'whatson': 2})
                    total = sum(len(events) for events in results.values())
                    logger.info(f"🔥 Firecrawl test: {total} events extracted")
                    return total
                
                result = asyncio.run(firecrawl_only())
                success = result > 0
            else:
                # Use enhanced_collection.py for all other cases
                success = asyncio.run(run_data_collection(
                    mode=args.mode,
                    enable_firecrawl=args.enable_firecrawl
                ))
            
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        logger.info("⚠️ Collection interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 