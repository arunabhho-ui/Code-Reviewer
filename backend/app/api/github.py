from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.models.schemas import OpenPRRequest, OpenPRResponse
from app.services.github_service import (
    inspect_github_target,
    fetch_github_file_content,
    create_pull_request_with_fix,
)

router = APIRouter(prefix="/api/github", tags=["github"])


class GitHubInspectRequest(BaseModel):
    url: str = Field(..., description="GitHub repository URL or Pull Request URL")
    github_token: Optional[str] = Field(None, description="Optional GitHub Personal Access Token")


class GitHubFetchFileRequest(BaseModel):
    owner: str
    repo: str
    path: str
    ref: Optional[str] = None
    github_token: Optional[str] = None


@router.post("/inspect")
async def inspect_target(request: GitHubInspectRequest):
    """
    Inspects a GitHub Repository or PR URL and returns changed/reviewable files.
    """
    try:
        data = await inspect_github_target(url=request.url, token=request.github_token)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to inspect GitHub target: {str(e)}")


@router.post("/fetch-file")
async def fetch_file(request: GitHubFetchFileRequest):
    """
    Fetches raw file contents from a GitHub repository or branch/commit.
    """
    try:
        filename, language, content = await fetch_github_file_content(
            owner=request.owner,
            repo=request.repo,
            path=request.path,
            ref=request.ref,
            token=request.github_token,
        )
        return {
            "filename": filename,
            "path": request.path,
            "language": language,
            "content": content,
            "owner": request.owner,
            "repo": request.repo,
            "ref": request.ref,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch GitHub file: {str(e)}")


@router.post("/open-pr", response_model=OpenPRResponse)
async def open_pull_request(request: OpenPRRequest):
    """
    Creates a new branch on GitHub, commits the sandbox-verified fix,
    and opens a pull request for human review.
    """
    try:
        result = await create_pull_request_with_fix(
            owner=request.owner,
            repo=request.repo,
            base_branch=request.base_branch,
            file_path=request.file_path,
            fixed_code=request.fixed_code,
            fix_summary=request.fix_summary or "Verified automated fix from AI Code Reviewer",
            finding_details=request.finding_details,
            test_verification_type=request.test_verification_type,
            github_token=request.github_token,
        )
        return OpenPRResponse(
            success=True,
            pr_url=result.get("pr_url"),
            pr_number=result.get("pr_number"),
            branch=result.get("branch"),
            message=result.get("message", "Pull Request opened successfully!"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open GitHub Pull Request: {str(e)}")

