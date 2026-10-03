from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

from app.api.routes.analyze import router as analyze_router
from app.api.routes.coach import router as coach_router

# Mount analyze router on /api and /api/v1 for convenience (backward compatibility)
app.include_router(analyze_router, prefix="/api", tags=["Analysis"])
app.include_router(analyze_router, prefix="/api/v1", tags=["Analysis"])

# Mount new candidate-facing coach router
app.include_router(coach_router, prefix="/api/coach", tags=["Coach"])
app.include_router(coach_router, prefix="/api/v1/coach", tags=["Coach"])

@app.get("/health")
def health_check():
    """
    Health check endpoint to verify backend is running locally.
    """
    return {"status": "ok", "app_name": settings.APP_NAME}
