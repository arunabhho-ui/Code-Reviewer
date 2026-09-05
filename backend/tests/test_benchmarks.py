import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_benchmarks_list_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/benchmarks/list")
        assert res.status_code == 200
        data = res.json()
        assert data["total_benchmarks"] == 8
        assert len(data["benchmarks"]) == 8


@pytest.mark.asyncio
async def test_benchmarks_run_single_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/benchmarks/run", json={"benchmark_id": "PY-01"})
        assert res.status_code == 200
        data = res.json()
        assert data["single"] is True
        assert data["result"]["id"] == "PY-01"
        assert data["result"]["baseline_bug_reproduced"] is True
        assert data["result"]["fix_verified_in_sandbox"] is True
