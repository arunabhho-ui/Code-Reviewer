import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.github_service import parse_github_url, detect_language_from_path


def test_parse_github_urls():
    # Standard repo
    r1 = parse_github_url("https://github.com/psf/requests")
    assert r1["type"] == "repo"
    assert r1["owner"] == "psf"
    assert r1["repo"] == "requests"

    # PR URL
    r2 = parse_github_url("https://github.com/psf/requests/pull/1234")
    assert r2["type"] == "pr"
    assert r2["owner"] == "psf"
    assert r2["repo"] == "requests"
    assert r2["pr_number"] == 1234

    # Tree branch URL
    r3 = parse_github_url("github.com/fastapi/fastapi/tree/master")
    assert r3["type"] == "repo"
    assert r3["ref"] == "master"


def test_detect_language():
    assert detect_language_from_path("src/app/main.py") == "python"
    assert detect_language_from_path("frontend/src/App.jsx") == "javascript"
    assert detect_language_from_path("backend/types.ts") == "typescript"
    assert detect_language_from_path("README.md") is None


@pytest.mark.asyncio
async def test_github_invalid_url_inspect():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/github/inspect", json={"url": "invalid-url"})
        assert res.status_code == 400
        assert "Invalid GitHub URL" in res.json()["detail"]
