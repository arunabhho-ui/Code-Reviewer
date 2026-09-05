import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api.review import clear_review_rate_limit_buckets, enforce_review_rate_limit
from app.services.static_analysis import run_static_analysis


def test_python_static_syntax_error():
    broken_code = "def foo(\n    print('missing closing paren')"
    findings = run_static_analysis(broken_code, "python")
    assert len(findings) > 0
    assert any("syntax" in f.message.lower() or f.severity == "critical" for f in findings)


def test_python_static_clean_code():
    clean_code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    findings = run_static_analysis(clean_code, "python")
    # Clean code should produce zero critical findings
    assert not any(f.severity == "critical" for f in findings)


def test_js_static_analysis():
    js_vuln_code = "function test(input) {\n    eval(input);\n    const element = document.getElementById('app');\n    element.innerHTML = input;\n}"
    findings = run_static_analysis(js_vuln_code, "javascript")
    assert len(findings) >= 2
    rules = [f.rule for f in findings]
    assert "JS-SECURITY-EVAL" in rules
    assert "JS-SECURITY-INNERHTML" in rules


@pytest.mark.asyncio
async def test_review_endpoint_payload():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "code": "def divide(a, b):\n    return a / b\n",
            "language": "python",
            "filename": "math_util.py",
            "run_static_analysis": True
        }
        response = await client.post("/api/review", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "findings" in data
        assert "summary" in data
        assert "execution_time_ms" in data
        assert data["language"] == "python"


def test_review_rate_limit_once_over_limit():
    clear_review_rate_limit_buckets()
    for _ in range(60):
        enforce_review_rate_limit("203.0.113.9", limit=60, window_seconds=3600)

    with pytest.raises(Exception):
        enforce_review_rate_limit("203.0.113.9", limit=60, window_seconds=3600)
