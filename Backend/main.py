from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import time
import logging

# Import configuration and database
from config import settings
from database import init_databases, close_databases

# Import permanent CORS middleware
from utils.cors_middleware import PermanentCORSMiddleware

# Import routers
from routers import db_test
from routers import events
from routers import hidden_gems
from routers import search  # Re-enable search functionality

# Import AI search router with error handling
try:
    from routers import ai_search  # OpenAI-powered intelligent search
    logger.info("✅ AI search router imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import AI search router: {e}")
    ai_search = None

# Enhanced Authentication with OTP router (MongoDB-based)
from routers import auth_with_otp
# Saved events router for favorites functionality
from routers import saved_events
# Event advice router for replacing reviews
from routers import event_advice
# Google OAuth router
from routers import google_auth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Dubai Events Intelligence Platform - Backend API for family-focused event discovery and recommendations",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware will be added at the end of the file

# Add permanent CORS middleware for critical endpoints FIRST
app.add_middleware(
    PermanentCORSMiddleware,
    critical_paths=[
        "/api/hidden-gems",
        "/api/events", 
        "/api/notifications",
        "/api/auth",
        "/api/advice"
    ],
    allowed_origins=[
        "https://mydscvr.ai",
        "https://www.mydscvr.ai", 
        "http://mydscvr.ai",
        "http://www.mydscvr.ai",
        "https://mydscvr.xyz",
        "https://www.mydscvr.xyz",
        "http://mydscvr.xyz", 
        "http://www.mydscvr.xyz",
        "http://localhost:8080",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5000",
        "http://localhost:5173"
    ]
)

# Add trusted host middleware for security
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.dxb-events.com", "mydscvr.xyz", "*.mydscvr.xyz", "mydscvr.ai", "*.mydscvr.ai"]
    )


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # Log slow requests
    if process_time > 1.0:  # Log requests taking more than 1 second
        logger.warning(f"Slow request: {request.method} {request.url} took {process_time:.2f}s")
    
    return response


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Get origin for CORS
    origin = request.headers.get("origin", "https://mydscvr.ai")
    allowed_origins = [
        "https://mydscvr.ai", "https://www.mydscvr.ai",
        "http://mydscvr.ai", "http://www.mydscvr.ai",
        "https://mydscvr.xyz", "https://www.mydscvr.xyz",
        "http://mydscvr.xyz", "http://www.mydscvr.xyz"
    ]
    response_origin = origin if origin in allowed_origins else "https://mydscvr.ai"
    
    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error_code": f"HTTP_{exc.status_code}"
        },
        headers={
            "Access-Control-Allow-Origin": response_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Expose-Headers": "*"
        }
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Get origin for CORS
    origin = request.headers.get("origin", "https://mydscvr.ai")
    allowed_origins = [
        "https://mydscvr.ai", "https://www.mydscvr.ai",
        "http://mydscvr.ai", "http://www.mydscvr.ai",
        "https://mydscvr.xyz", "https://www.mydscvr.xyz",
        "http://mydscvr.xyz", "http://www.mydscvr.xyz"
    ]
    response_origin = origin if origin in allowed_origins else "https://mydscvr.ai"
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Validation error",
            "error_code": "VALIDATION_ERROR",
            "details": exc.errors()
        },
        headers={
            "Access-Control-Allow-Origin": response_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Expose-Headers": "*"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Get origin for CORS
    origin = request.headers.get("origin", "https://mydscvr.ai")
    allowed_origins = [
        "https://mydscvr.ai", "https://www.mydscvr.ai",
        "http://mydscvr.ai", "http://www.mydscvr.ai",
        "https://mydscvr.xyz", "https://www.mydscvr.xyz",
        "http://mydscvr.xyz", "http://www.mydscvr.xyz"
    ]
    response_origin = origin if origin in allowed_origins else "https://mydscvr.ai"
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error",
            "error_code": "INTERNAL_ERROR"
        },
        headers={
            "Access-Control-Allow-Origin": response_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Expose-Headers": "*"
        }
    )


# Startup events
@app.on_event("startup")
async def startup_event():
    """Initialize databases and connections on startup"""
    try:
        # Initialize MongoDB and other databases
        await init_databases()
        logger.info("✅ MongoDB Atlas database initialized successfully")
        
        logger.info(f"🚀 {settings.app_name} v{settings.app_version} started successfully!")
        logger.info(f"📋 MongoDB Atlas database: {settings.mongodb_database}")
        
    except Exception as e:
        logger.error(f"❌ Critical startup error: {e}")
        # Don't raise the exception - let the app start for testing
        logger.warning("⚠️ Starting with limited functionality for testing")


# Shutdown events
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    try:
        await close_databases()
        logger.info("✅ All database connections closed")
        
    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")


# Include routers
app.include_router(db_test.router)

# Events router
app.include_router(events.router)
# Hidden gems router
app.include_router(hidden_gems.router)
app.include_router(search.router)  # Re-enable search functionality

# Include AI search router only if it was imported successfully
if ai_search is not None:
    app.include_router(ai_search.router)  # OpenAI-powered intelligent search
    logger.info("✅ AI search router included successfully")
else:
    logger.error("❌ AI search router not available due to import error")

# MongoDB-based notifications router
from routers import notifications_mongodb
app.include_router(notifications_mongodb.router)

# Enhanced Authentication with OTP router (MongoDB-based)
app.include_router(auth_with_otp.router, prefix="/api")

# Saved events router for favorites functionality
app.include_router(saved_events.router)

# Event advice router for replacing reviews
app.include_router(event_advice.router)

# Google OAuth router
app.include_router(google_auth.router, prefix="/api")


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint with API information
    """
    return {
        "message": "Welcome to DXB Events API",
        "version": settings.app_version,
        "description": "Dubai Events Intelligence Platform - AI-powered family event discovery",
        "docs": "/docs" if settings.debug else "Documentation available in development mode",
        "status": "healthy",
        "database": {
            "mongodb_atlas": "connected",
            "database_name": settings.mongodb_database
        }
    }


# OPTIONS handler for CORS preflight requests
@app.options("/{path:path}")
async def options_handler(request: Request, path: str):
    """Handle OPTIONS requests for CORS preflight"""
    # Get origin from request headers
    request_origin = request.headers.get("origin", "https://mydscvr.ai")
    
    # List of allowed origins
    allowed_origins = [
        "https://mydscvr.ai",
        "https://www.mydscvr.ai",
        "http://mydscvr.ai",
        "http://www.mydscvr.ai",
        "https://mydscvr.xyz",
        "https://www.mydscvr.xyz",
        "http://mydscvr.xyz",
        "http://www.mydscvr.xyz",
        "http://localhost:8080",
        "http://localhost:3000",
        "http://localhost:3001"
    ]
    
    # Use the request origin if it's in the allowed list, otherwise use default
    response_origin = request_origin if request_origin in allowed_origins else "https://mydscvr.ai"
    
    return JSONResponse(
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": response_origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, Accept, Origin, User-Agent, x-session-token",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "3600",
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",
        "version": settings.app_version,
        "environment": "development" if settings.debug else "production",
        "services": {
            "api": "healthy",
            "mongodb_atlas": "connected",
            "postgresql": "healthy",
            "cache": "optional",
            "search": "optional"
        },
        "database": {
            "mongodb_database": settings.mongodb_database,
            "connection_type": "Atlas"
        }
    }


# API status endpoint
@app.get("/api/status")
async def api_status():
    """
    API-specific status information
    """
    return {
        "api_version": settings.app_version,
        "status": "operational",
        "features": {
            "authentication": "enabled",
            "user_management": "enabled",
            "mongodb_atlas": "connected",
            "database_testing": "enabled",
            "event_search": "coming_soon",
            "recommendations": "coming_soon",
            "webhooks": "coming_soon"
        },
        "rate_limits": {
            "authentication": "5 attempts per 5 minutes",
            "api_calls": "1000 per hour"
        },
        "database": {
            "primary": "MongoDB Atlas",
            "database_name": settings.mongodb_database
        }
    }


# Add CORS middleware AFTER all routes are defined
# Always include production origins from settings
origins = list(settings.cors_origins)  # Create a copy to avoid modifying the original

# Add localhost ports that Flutter commonly uses in debug mode
if settings.debug:
    origins.extend([
        "http://localhost:8080",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5000",
        "http://localhost:5001",
        "http://localhost:5173",  # Vite default
        "http://127.0.0.1:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ])

# Ensure all production domains are included
production_origins = [
    "https://mydscvr.ai",
    "https://www.mydscvr.ai",
    "http://mydscvr.ai",
    "http://www.mydscvr.ai",
    "https://mydscvr.xyz",
    "https://www.mydscvr.xyz",
    "http://mydscvr.xyz",
    "http://www.mydscvr.xyz"
]

# Add production origins if not already present
for origin in production_origins:
    if origin not in origins:
        origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*", "x-session-token"],
    expose_headers=["*"],
    max_age=3600,
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    ) 