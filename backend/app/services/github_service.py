import base64
import re
from typing import Dict, Any, List, Optional, Tuple
import httpx


GITHUB_API_BASE = "https://api.github.com"
SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}


def parse_github_url(url: str) -> Dict[str, Any]:
    """
    Parses a GitHub URL into owner, repo, and optionally pr_number or branch/ref.
    Supports:
    - https://github.com/owner/repo
    - https://github.com/owner/repo/pull/123
    - https://github.com/owner/repo/tree/branch
    """
    cleaned = url.strip().rstrip("/")
    # Clean protocols
    cleaned = re.sub(r"^https?://", "", cleaned)
    cleaned = re.sub(r"^github\.com/", "", cleaned)

    parts = cleaned.split("/")
    if len(parts) < 2:
        raise ValueError("Invalid GitHub URL. Format must be 'owner/repo' or 'https://github.com/owner/repo'")

    owner = parts[0]
    repo = parts[1]

    # Check for PR URL: owner/repo/pull/123
    if len(parts) >= 4 and parts[2] == "pull":
        try:
            pr_number = int(parts[3])
            return {
                "type": "pr",
                "owner": owner,
                "repo": repo,
                "pr_number": pr_number,
            }
        except ValueError:
            raise ValueError(f"Invalid PR number in URL: {parts[3]}")

    # Check for branch URL: owner/repo/tree/main
    ref = None
    if len(parts) >= 4 and parts[2] == "tree":
        ref = "/".join(parts[3:])

    return {
        "type": "repo",
        "owner": owner,
        "repo": repo,
        "ref": ref,
    }


def detect_language_from_path(path: str) -> Optional[str]:
    """Returns supported language name or None if unsupported."""
    lower = path.lower()
    for ext, lang in SUPPORTED_EXTENSIONS.items():
        if lower.endswith(ext):
            return lang
    return None


def get_headers(token: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-Code-Reviewer-App",
    }
    if token and token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"
    return headers


async def inspect_github_target(
    url: str,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Inspects a GitHub repo or PR URL and returns metadata plus the list of reviewable files.
    """
    parsed = parse_github_url(url)
    headers = get_headers(token)

    async with httpx.AsyncClient(timeout=15.0) as client:
        if parsed["type"] == "pr":
            owner = parsed["owner"]
            repo = parsed["repo"]
            pr_num = parsed["pr_number"]

            # 1. Fetch PR details
            pr_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_num}"
            pr_res = await client.get(pr_url, headers=headers)
            if pr_res.status_code == 404:
                raise ValueError(f"GitHub Pull Request #{pr_num} not found in repository {owner}/{repo}.")
            elif pr_res.status_code == 403:
                raise ValueError("GitHub API rate limit exceeded or access forbidden. Please provide a GitHub Personal Access Token.")
            elif pr_res.status_code != 200:
                raise ValueError(f"GitHub API returned error {pr_res.status_code}: {pr_res.text}")

            pr_data = pr_res.json()
            head_sha = pr_data.get("head", {}).get("sha", "main")
            pr_title = pr_data.get("title", f"Pull Request #{pr_num}")

            # 2. Fetch changed files in PR
            files_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_num}/files"
            files_res = await client.get(files_url, headers=headers)
            if files_res.status_code != 200:
                raise ValueError(f"Failed to fetch PR changed files: {files_res.text}")

            files_data = files_res.json()
            reviewable_files = []

            for f in files_data:
                filename = f.get("filename", "")
                lang = detect_language_from_path(filename)
                if lang:
                    reviewable_files.append({
                        "filename": filename.split("/")[-1],
                        "path": filename,
                        "language": lang,
                        "status": f.get("status", "modified"),
                        "additions": f.get("additions", 0),
                        "deletions": f.get("deletions", 0),
                        "changes": f.get("changes", 0),
                        "patch": f.get("patch"),
                        "raw_url": f.get("raw_url"),
                        "sha": head_sha,
                    })

            return {
                "type": "pr",
                "owner": owner,
                "repo": repo,
                "pr_number": pr_num,
                "title": pr_title,
                "head_sha": head_sha,
                "base_branch": pr_data.get("base", {}).get("ref", "main"),
                "total_changed_files": len(files_data),
                "reviewable_files": reviewable_files,
            }

        else:
            # Repo mode
            owner = parsed["owner"]
            repo = parsed["repo"]
            ref = parsed.get("ref")

            # 1. Fetch repo metadata
            repo_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
            repo_res = await client.get(repo_url, headers=headers)
            if repo_res.status_code == 404:
                raise ValueError(f"GitHub repository {owner}/{repo} not found.")
            elif repo_res.status_code == 403:
                raise ValueError("GitHub API rate limit exceeded or access forbidden. Please provide a GitHub Personal Access Token.")
            elif repo_res.status_code != 200:
                raise ValueError(f"GitHub API returned error {repo_res.status_code}: {repo_res.text}")

            repo_data = repo_res.json()
            default_branch = ref or repo_data.get("default_branch", "main")

            # 2. Fetch Git Tree recursively
            tree_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
            tree_res = await client.get(tree_url, headers=headers)
            if tree_res.status_code != 200:
                raise ValueError(f"Failed to fetch repository tree: {tree_res.text}")

            tree_data = tree_res.json()
            tree_items = tree_data.get("tree", [])

            reviewable_files = []
            for item in tree_items:
                if item.get("type") == "blob":
                    path = item.get("path", "")
                    lang = detect_language_from_path(path)
                    if lang and not path.startswith(("node_modules/", "venv/", ".venv/", "dist/", "build/")):
                        reviewable_files.append({
                            "filename": path.split("/")[-1],
                            "path": path,
                            "language": lang,
                            "size": item.get("size", 0),
                            "sha": default_branch,
                        })

            return {
                "type": "repo",
                "owner": owner,
                "repo": repo,
                "title": repo_data.get("description") or f"{owner}/{repo}",
                "default_branch": default_branch,
                "stars": repo_data.get("stargazers_count", 0),
                "total_files": len(tree_items),
                "reviewable_files": reviewable_files[:100],  # cap at top 100 files
            }


async def fetch_github_file_content(
    owner: str,
    repo: str,
    path: str,
    ref: Optional[str] = None,
    token: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Fetches the raw content of a specific file from GitHub.
    Returns (filename, language, content).
    """
    headers = get_headers(token)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    params = {}
    if ref:
        params["ref"] = ref

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(url, headers=headers, params=params)
        if res.status_code == 404:
            raise ValueError(f"File '{path}' not found in {owner}/{repo} at ref '{ref or 'default'}'.")
        elif res.status_code == 403:
            raise ValueError("GitHub API rate limit exceeded. Please provide a GitHub Personal Access Token.")
        elif res.status_code != 200:
            raise ValueError(f"GitHub API error {res.status_code}: {res.text}")

        data = res.json()
        encoding = data.get("encoding", "")
        raw_content = data.get("content", "")

        if encoding == "base64":
            content = base64.b64decode(raw_content).decode("utf-8", errors="replace")
        else:
            content = raw_content

        filename = path.split("/")[-1]
        language = detect_language_from_path(filename) or "python"

        return filename, language, content


async def create_pull_request_with_fix(
    owner: str,
    repo: str,
    file_path: str,
    fixed_code: str,
    fix_summary: str,
    github_token: str,
    base_branch: Optional[str] = None,
    finding_details: Optional[Dict[str, Any]] = None,
    test_verification_type: str = "smoke_test",
) -> Dict[str, Any]:
    """
    Creates a new branch, commits the sandbox-verified fix, and opens a GitHub Pull Request.
    Includes honest provenance (pre-existing tests vs generated smoke tests) and AI review disclaimer.
    """
    import time
    if not github_token or not github_token.strip():
        raise ValueError("GitHub Personal Access Token is required to open a pull request.")

    headers = get_headers(github_token)
    finding = finding_details or {}
    finding_title = finding.get("title") or finding.get("vulnerability_type") or "Fix code issue"
    severity = finding.get("severity", "medium").upper()
    category = finding.get("category") or ("security" if finding.get("vulnerability_type") else "bug")

    async with httpx.AsyncClient(timeout=20.0) as client:
        # 1. Resolve default base branch if not explicitly provided
        target_base = base_branch
        if not target_base or target_base.strip() == "":
            repo_res = await client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}", headers=headers)
            if repo_res.status_code == 401:
                raise ValueError("Invalid or expired GitHub Personal Access Token. Please verify your token.")
            elif repo_res.status_code == 404:
                raise ValueError(f"GitHub repository '{owner}/{repo}' not found. Please check repository name and access.")
            elif repo_res.status_code == 403:
                raise ValueError("GitHub API access forbidden or rate limit exceeded. Verify token permissions (needs repo or contents/pull-requests scope).")
            elif repo_res.status_code != 200:
                raise ValueError(f"Failed to fetch repository details: {repo_res.text}")
            repo_data = repo_res.json()
            target_base = repo_data.get("default_branch", "main")

        # 2. Get the commit SHA of the base branch
        ref_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/ref/heads/{target_base}"
        ref_res = await client.get(ref_url, headers=headers)
        if ref_res.status_code == 404:
            raise ValueError(f"Base branch '{target_base}' was not found in repository '{owner}/{repo}'.")
        elif ref_res.status_code == 401:
            raise ValueError("Invalid or expired GitHub Personal Access Token.")
        elif ref_res.status_code == 403:
            raise ValueError("GitHub API forbidden: Insufficient permissions on repository to create branches or pull requests.")
        elif ref_res.status_code != 200:
            raise ValueError(f"Failed to inspect base branch '{target_base}': {ref_res.text}")

        base_sha = ref_res.json().get("object", {}).get("sha")
        if not base_sha:
            raise ValueError(f"Could not resolve commit SHA for base branch '{target_base}'.")

        # 3. Create a unique new branch
        slug_seed = finding.get("vulnerability_type") or finding_title
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug_seed.strip()).strip("-").lower()[:28] or "verified-fix"
        timestamp = int(time.time())
        new_branch = f"ai-review-fix/{slug}-{timestamp}"

        create_ref_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/refs"
        create_ref_payload = {
            "ref": f"refs/heads/{new_branch}",
            "sha": base_sha,
        }
        create_ref_res = await client.post(create_ref_url, headers=headers, json=create_ref_payload)
        if create_ref_res.status_code == 422:
            raise ValueError(f"Branch '{new_branch}' already exists or branch reference could not be created.")
        elif create_ref_res.status_code != 201:
            raise ValueError(f"Failed to create new branch '{new_branch}': {create_ref_res.text}")

        # 4. Get the existing file's blob SHA (needed for PUT contents update)
        contents_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{file_path}"
        contents_res = await client.get(contents_url, headers=headers, params={"ref": target_base})
        file_sha = None
        if contents_res.status_code == 200:
            file_sha = contents_res.json().get("sha")

        # 5. Commit the verified fix to the new branch
        encoded_content = base64.b64encode(fixed_code.encode("utf-8")).decode("ascii")
        commit_message = f"fix(ai-review): {finding_title} in {file_path}"
        commit_payload: Dict[str, Any] = {
            "message": commit_message,
            "content": encoded_content,
            "branch": new_branch,
        }
        if file_sha:
            commit_payload["sha"] = file_sha

        commit_res = await client.put(contents_url, headers=headers, json=commit_payload)
        if commit_res.status_code in (409, 422):
            raise ValueError(f"Merge conflict or state error while committing to branch '{new_branch}': {commit_res.text}")
        elif commit_res.status_code not in (200, 201):
            raise ValueError(f"Failed to commit verified fix to branch '{new_branch}': {commit_res.text}")

        # 6. Format honest PR description
        if test_verification_type == "pre_existing":
            test_badge = "✅ **Pre-Existing Test Suite Passed**"
            test_explanation = "This patch was executed and verified against the repository's pre-existing automated test suite inside an isolated sandbox container."
        else:
            test_badge = "✅ **Autonomous Smoke Test Passed**"
            test_explanation = "This patch was executed and verified against an autonomous, LLM-generated smoke test suite inside an isolated sandbox container (no pre-existing test suite was configured)."

        pr_title = f"fix(ai-review): [{severity}] {finding_title}"
        pr_body = f"""## 🤖 AI Code Reviewer — Automated Fix Proposal

### 📌 Addressed Finding
- **Category**: `{category.upper()}`
- **Severity**: `{severity}`
- **File**: `{file_path}`
- **Issue**: {finding_title}

### 💡 Summary of Changes
{fix_summary}

### 🛡️ Sandboxed Test Verification
- **Status**: {test_badge}
- **Verification Details**: {test_explanation}
> **Trust & Transparency**: All test assertions passed cleanly in an isolated execution sandbox before this Pull Request was opened.

---
⚠️ **Human Review Required**: This pull request was created automatically by **AI Code Reviewer**. Autonomous merging is strictly disabled. Please perform standard human review, regression checks, and security evaluation before merging into `{target_base}`.
"""

        # 7. Open Pull Request via GitHub API
        pull_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
        pull_payload = {
            "title": pr_title,
            "head": new_branch,
            "base": target_base,
            "body": pr_body,
            "maintainer_can_modify": True,
        }
        pull_res = await client.post(pull_url, headers=headers, json=pull_payload)
        if pull_res.status_code == 422:
            err_data = pull_res.json()
            err_msg = err_data.get("message", "Validation failed")
            if "errors" in err_data:
                err_msg += f": {err_data['errors']}"
            raise ValueError(f"GitHub Pull Request creation failed: {err_msg}")
        elif pull_res.status_code != 201:
            raise ValueError(f"Failed to open Pull Request on GitHub: {pull_res.text}")

        pr_data = pull_res.json()
        pr_html_url = pr_data.get("html_url")
        pr_number = pr_data.get("number")

        return {
            "success": True,
            "pr_url": pr_html_url,
            "pr_number": pr_number,
            "branch": new_branch,
            "message": f"Successfully created Pull Request #{pr_number} on branch '{new_branch}'",
        }

