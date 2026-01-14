#!/usr/bin/env python3
"""
Store Feedback API - Secure Server with JWT Authentication
Production-ready FastAPI application with security middleware
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
import secrets

from app.core.config import get_settings, init_directories
from app.services.database import Database, get_database
from app.api import auth, feedback, dashboard, stores

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - DB connections and initialization"""
    # Startup
    await Database.connect()
    init_directories()
    print(f"✓ {settings.APP_NAME} started successfully")
    print(f"✓ API available at: {settings.API_V1_PREFIX}")
    yield
    # Shutdown
    await Database.disconnect()
    print("✓ Application shutdown complete")


# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Secure API for collecting and analyzing retail store staff feedback",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,  # Disable docs in production
    redoc_url="/api/redoc" if settings.DEBUG else None,
)


# ============ Security Middleware ============

# 1. Trusted Host Middleware - Prevent host header attacks
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["store-feedback.tarsyer.com", "*.tarsyer.com"]
    )

# 2. CORS Middleware - Restrict cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Length", "Content-Type"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# 3. Session Middleware - Secure session handling
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.JWT_SECRET_KEY,
    session_cookie="session",
    max_age=3600,  # 1 hour
    same_site="lax",
    https_only=not settings.DEBUG,  # HTTPS only in production
)

# 4. GZip Middleware - Compress responses
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ============ Security Headers Middleware ============

@app.middleware("http")
async def add_security_headers(request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)

    # Security headers for production
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    # Strict Transport Security (HSTS) - only over HTTPS
    if not settings.DEBUG and request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self' https://kwen.tarsyer.com; "
        "media-src 'self' blob:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    return response


# ============ API Routers ============

# Include API routers with JWT protection
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(feedback.router, prefix=settings.API_V1_PREFIX)
app.include_router(dashboard.router, prefix=settings.API_V1_PREFIX)
app.include_router(stores.router, prefix=settings.API_V1_PREFIX)


# ============ Static Files ============

# Serve uploaded media files (authentication handled in routes)
try:
    app.mount("/media", StaticFiles(directory=settings.UPLOAD_DIR), name="media")
except RuntimeError:
    print(f"⚠ Warning: Upload directory not found: {settings.UPLOAD_DIR}")


# ============ Health Check ============

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "environment": "development" if settings.DEBUG else "production"
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Store Feedback API",
        "version": "2.0.0",
        "docs": f"{settings.API_V1_PREFIX}/docs" if settings.DEBUG else "disabled",
        "health": "/health"
    }


# ============ Error Handlers ============

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler"""
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found"}
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Custom 500 handler"""
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
        access_log=True,
        server_header=False,  # Hide server header
        date_header=False,    # Hide date header
    )
