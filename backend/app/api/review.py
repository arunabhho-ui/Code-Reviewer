import time
import uuid
from collections import defaultdict, deque
from fastapi import APIRouter, HTTPException, Request
from app.models.schemas import ReviewRequest, ReviewResponse, ReviewSummary
from app.services.static_analysis import run_static_analysis
from app.services.llm_service import review_code_with_llm
from app.services.security_service import run_dedicated_security_review

router = APIRouter(prefix="/api", tags=["review"])

REVIEW_RATE_LIMIT = 60
REVIEW_RATE_LIMIT_WINDOW_SECONDS = 60 * 60
_review_buckets = defaultdict(deque)


def clear_review_rate_limit_buckets():
    _review_buckets.clear()


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_review_rate_limit(client_ip: str, limit: int = REVIEW_RATE_LIMIT, window_seconds: int = REVIEW_RATE_LIMIT_WINDOW_SECONDS):
    now = time.time()
    bucket = _review_buckets[client_ip]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()

    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded for review endpoint: {limit} requests per {window_seconds // 3600} hour(s) per IP."
        )

    bucket.append(now)


@router.post("/review", response_model=ReviewResponse)
async def review_code(request: ReviewRequest, http_request: Request):
    """
    Analyzes code snippet via deterministic static analysis pass,
    followed by Groq deep code review with structured findings.
    """
    client_ip = get_client_ip(http_request)
    enforce_review_rate_limit(client_ip)

    start_time = time.time()
    default_filenames = {
        "python": "snippet.py",
        "javascript": "snippet.js",
        "typescript": "snippet.ts",
        "c": "snippet.c",
        "java": "Snippet.java",
    }
    filename = request.filename or default_filenames[request.language]

    try:
        # Step 1: Static analysis pass
        static_findings = []
        if request.run_static_analysis:
            static_findings = run_static_analysis(
                code=request.code,
                language=request.language,
                filename=filename
            )

        # Step 2: LLM structured review
        findings, summary, raw_fixed_code, token_usage, warning_msg = await review_code_with_llm(
            code=request.code,
            language=request.language,
            filename=filename,
            static_findings=static_findings,
            api_key_override=request.api_key,
            model_override=request.model,
        )

        # Step 3: Dedicated Security Review Pass (scoped to GitHub PR Mode & Whole-Repo RAG Mode)
        security_findings = None
        security_summary = None
        if request.run_security_pass:
            sec_findings, sec_summary = await run_dedicated_security_review(
                code=request.code,
                language=request.language,
                filename=filename,
                api_key_override=request.api_key,
                model_override=request.model,
            )
            security_findings = sec_findings
            security_summary = sec_summary

        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return ReviewResponse(
            id=str(uuid.uuid4()),
            filename=filename,
            language=request.language,
            static_findings=static_findings,
            findings=findings,
            security_findings=security_findings,
            security_summary=security_summary,
            summary=summary,
            execution_time_ms=elapsed_ms,
            token_usage=token_usage,
            raw_fixed_code=raw_fixed_code,
            warning=warning_msg,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during code review: {str(e)}"
        )
