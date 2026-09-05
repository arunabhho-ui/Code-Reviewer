import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.rag_service import (
    chunk_python_file,
    chunk_javascript_file,
    index_repository_files,
    retrieve_cross_file_context,
)


def test_python_ast_chunking():
    py_code = """
class BaseHandler:
    def handle(self):
        pass

def calculate_tax(amount: float, rate: float) -> float:
    \"\"\"Calculates tax amount.\"\"\"
    multiplier = get_rate_multiplier(rate)
    return amount * multiplier

async def process_transaction(tx_id: str):
    log_event(tx_id)
    return True
"""
    chunks = chunk_python_file(py_code, "services/tax.py")
    assert len(chunks) == 3
    symbols = {c.symbol_name for c in chunks}
    assert "BaseHandler" in symbols
    assert "calculate_tax" in symbols
    assert "process_transaction" in symbols

    # Check function call extraction
    tax_chunk = next(c for c in chunks if c.symbol_name == "calculate_tax")
    assert "get_rate_multiplier" in tax_chunk.calls
    assert tax_chunk.docstring == "Calculates tax amount."


def test_chroma_indexing_and_cross_file_retrieval():
    files = [
        {
            "path": "auth/crypto.py",
            "language": "python",
            "content": """
def insecure_md5_hash(password: str) -> str:
    \"\"\"Legacy hash function.\"\"\"
    import hashlib
    return hashlib.md5(password.encode()).hexdigest()
""",
        },
        {
            "path": "auth/service.py",
            "language": "python",
            "content": """
from auth.crypto import insecure_md5_hash

def register_user(username, password):
    # Calls insecure_md5_hash from crypto.py
    hashed = insecure_md5_hash(password)
    return {"user": username, "hash": hashed}
""",
        },
    ]

    index_res = index_repository_files("test_auth_repo", files)
    assert index_res["total_files"] == 2
    assert index_res["total_chunks"] >= 2

    # Now retrieve cross-file context for service.py
    target_code = files[1]["content"]
    retrieved = retrieve_cross_file_context(
        repo_name="test_auth_repo",
        target_file_path="auth/service.py",
        target_code=target_code,
        language="python",
        top_k=2,
    )

    assert len(retrieved) > 0
    # Must retrieve chunk from auth/crypto.py and NOT auth/service.py
    assert all(r["file_path"] == "auth/crypto.py" for r in retrieved)
    assert any(r["symbol_name"] == "insecure_md5_hash" for r in retrieved)


@pytest.mark.asyncio
async def test_rag_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Index
        index_payload = {
            "repo_name": "demo_api_repo",
            "files": [
                {"path": "utils/math.py", "content": "def add(a, b): return a + b\n", "language": "python"},
                {"path": "main.py", "content": "from utils.math import add\n\ndef run(): return add(1, 2)\n", "language": "python"},
            ],
        }
        res1 = await client.post("/api/rag/index", json=index_payload)
        assert res1.status_code == 200
        assert res1.json()["total_files"] == 2

        # 2. Query
        query_payload = {
            "repo_name": "demo_api_repo",
            "target_file_path": "main.py",
            "code": "from utils.math import add\n\ndef run(): return add(1, 2)\n",
            "language": "python",
            "top_k": 2,
        }
        res2 = await client.post("/api/rag/query", json=query_payload)
        assert res2.status_code == 200
        data = res2.json()
        assert "cross_file_chunks" in data
