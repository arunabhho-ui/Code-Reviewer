import time
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.schemas import ReviewResponse
from app.services.static_analysis import run_static_analysis
from app.services.llm_service import review_code_with_llm
from app.services.security_service import run_dedicated_security_review
from app.services.rag_service import index_repository_files, retrieve_cross_file_context

router = APIRouter(prefix="/api/rag", tags=["rag"])


class RepoFilePayload(BaseModel):
    path: str
    content: str
    language: Optional[str] = "python"


class RAGIndexRequest(BaseModel):
    repo_name: str
    files: List[RepoFilePayload]


class RAGQueryRequest(BaseModel):
    repo_name: str
    target_file_path: str
    code: str
    language: str = "python"
    top_k: int = 4


class RAGReviewRequest(BaseModel):
    repo_name: str
    target_file_path: str
    code: str
    language: str = "python"
    api_key: Optional[str] = None
    model: Optional[str] = None
    run_static_analysis: bool = True
    run_security_pass: bool = True
    top_k_context: int = 4


@router.post("/index")
async def index_repo(request: RAGIndexRequest):
    """
    Indexes repository files into ChromaDB at AST function/class symbol granularity.
    """
    try:
        files_dict = [
            {"path": f.path, "content": f.content, "language": f.language or "python"}
            for f in request.files
        ]
        result = index_repository_files(request.repo_name, files_dict)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to index repository: {str(e)}")


@router.post("/query")
async def query_context(request: RAGQueryRequest):
    """
    Retrieves relevant cross-file context chunks for a target file under review.
    """
    try:
        chunks = retrieve_cross_file_context(
            repo_name=request.repo_name,
            target_file_path=request.target_file_path,
            target_code=request.code,
            language=request.language,
            top_k=request.top_k,
        )
        return {
            "repo_name": request.repo_name,
            "target_file_path": request.target_file_path,
            "cross_file_chunks": chunks,
            "total_retrieved": len(chunks),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query RAG context: {str(e)}")


@router.post("/review")
async def review_with_rag(request: RAGReviewRequest):
    """
    Runs code review on a target file with cross-file context retrieved from Chroma vector store.
    """
    start_time = time.time()
    filename = request.target_file_path.split("/")[-1]

    try:
        # 1. Retrieve cross-file dependencies from Chroma
        cross_context = retrieve_cross_file_context(
            repo_name=request.repo_name,
            target_file_path=request.target_file_path,
            target_code=request.code,
            language=request.language,
            top_k=request.top_k_context,
        )

        # 2. Static analysis pass
        static_findings = []
        if request.run_static_analysis:
            static_findings = run_static_analysis(
                code=request.code,
                language=request.language,
                filename=filename,
            )

        # 3. LLM review with cross-file context
        findings, summary, raw_fixed_code, token_usage, warning_msg = await review_code_with_llm(
            code=request.code,
            language=request.language,
            filename=filename,
            static_findings=static_findings,
            api_key_override=request.api_key,
            model_override=request.model,
            cross_file_context=cross_context,
        )

        # 4. Dedicated Security Review Pass with cross-file context
        security_findings = None
        security_summary = None
        if request.run_security_pass:
            sec_findings, sec_summary = await run_dedicated_security_review(
                code=request.code,
                language=request.language,
                filename=filename,
                api_key_override=request.api_key,
                model_override=request.model,
                cross_file_context=cross_context,
            )
            security_findings = sec_findings
            security_summary = sec_summary

        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "review": ReviewResponse(
                id=str(uuid.uuid4()),
                filename=filename,
                language=request.language,  # type: ignore
                static_findings=static_findings,
                findings=findings,
                security_findings=security_findings,
                security_summary=security_summary,
                summary=summary,
                execution_time_ms=elapsed_ms,
                token_usage=token_usage,
                raw_fixed_code=raw_fixed_code,
                warning=warning_msg,
            ),
            "cross_file_context": cross_context,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG review failed: {str(e)}")
