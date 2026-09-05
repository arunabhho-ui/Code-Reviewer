import os
import sys
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Ensure root workspace and benchmarks directory are in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
benchmarks_dir = os.path.join(root_dir, "benchmarks")
if benchmarks_dir not in sys.path:
    sys.path.insert(0, benchmarks_dir)

from dataset import BENCHMARK_SUITE
from evaluate import evaluate_single_benchmark, run_evaluation_suite

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])


class RunBenchmarkRequest(BaseModel):
    benchmark_id: Optional[str] = Field(None, description="Optional specific benchmark ID (e.g. PY-01), or None to run all")
    api_key: Optional[str] = None


@router.get("/list")
async def list_benchmarks():
    """
    Returns the complete benchmark suite metadata and snippets.
    """
    return {
        "total_benchmarks": len(BENCHMARK_SUITE),
        "benchmarks": BENCHMARK_SUITE,
    }


@router.post("/run")
async def run_benchmarks(request: RunBenchmarkRequest):
    """
    Executes benchmark tests inside the sandbox and returns concrete metrics.
    """
    try:
        if request.benchmark_id:
            # Run single benchmark
            bm = next((b for b in BENCHMARK_SUITE if b["id"] == request.benchmark_id), None)
            if not bm:
                raise HTTPException(status_code=404, detail=f"Benchmark '{request.benchmark_id}' not found")
            result = await evaluate_single_benchmark(bm, api_key=request.api_key)
            return {"single": True, "result": result}
        else:
            # Run all benchmarks
            report = await run_evaluation_suite(api_key=request.api_key)
            return {"single": False, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Benchmark execution failed: {str(e)}")
