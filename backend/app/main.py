from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import health, review, agent, github, rag, benchmarks

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for AI Code Reviewer & Bug Fixing Agent",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router)
app.include_router(review.router)
app.include_router(agent.router)
app.include_router(github.router)
app.include_router(rag.router)
app.include_router(benchmarks.router)


@app.get("/")
async def root():
    return {
        "message": "AI Code Reviewer & Bug Fixing Agent API is running.",
        "docs": "/docs",
        "health": "/health",
        "review_endpoint": "/api/review",
        "agent_stream_endpoint": "/api/agent/fix/stream",
        "github_inspect_endpoint": "/api/github/inspect",
        "rag_index_endpoint": "/api/rag/index",
        "benchmarks_list_endpoint": "/api/benchmarks/list",
    }
