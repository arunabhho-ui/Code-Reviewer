import json
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import AgentFixRequest, AgentFixResponse, TokenUsage
from app.services.agent_loop import run_agent_fix_stream

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/fix/stream")
async def stream_agent_fix(request: AgentFixRequest):
    """
    SSE stream endpoint for the autonomous bug-fixing agent loop.
    Emits real-time reasoning steps, patch diffs, sandbox runs, and verified outcomes.
    """
    async def event_generator():
        try:
            async for step in run_agent_fix_stream(
                code=request.code,
                language=request.language,
                filename=request.filename or "solution.py",
                bug_description=request.bug_description,
                test_code=request.test_code,
                api_key=request.api_key,
                model_override=request.model,
                max_retries=request.max_retries,
            ):
                event_name = step.get("event", "message")
                payload = json.dumps(step.get("data", {}))
                yield f"event: {event_name}\ndata: {payload}\n\n"
        except Exception as e:
            err_data = json.dumps({"message": f"Server streaming exception: {str(e)}", "fatal": True})
            yield f"event: error\ndata: {err_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/fix", response_model=AgentFixResponse)
async def run_agent_fix_sync(request: AgentFixRequest):
    """
    Synchronous execution of the agent loop returning complete results and all steps.
    """
    steps = []
    final_result = None

    try:
        async for step in run_agent_fix_stream(
            code=request.code,
            language=request.language,
            filename=request.filename or "solution.py",
            bug_description=request.bug_description,
            test_code=request.test_code,
            api_key=request.api_key,
            model_override=request.model,
            max_retries=request.max_retries,
        ):
            steps.append(step)
            if step.get("event") == "agent_completed":
                final_result = step.get("data")
            elif step.get("event") == "error" and step.get("data", {}).get("fatal"):
                raise HTTPException(status_code=400, detail=step["data"]["message"])

        if not final_result:
            return AgentFixResponse(
                success=False,
                verified_in_sandbox=False,
                total_attempts=0,
                final_code=request.code,
                message="Agent execution finished without final outcome.",
                steps=steps
            )

        token_data = final_result.get("tokens", {})
        return AgentFixResponse(
            success=final_result.get("success", False),
            verified_in_sandbox=final_result.get("verified_in_sandbox", False),
            total_attempts=final_result.get("total_attempts", 0),
            final_code=final_result.get("final_code", request.code),
            final_diff=final_result.get("final_diff"),
            test_code=final_result.get("test_code"),
            test_type=final_result.get("test_type", "smoke_test"),
            token_usage=TokenUsage(
                input_tokens=token_data.get("input_tokens", 0),
                output_tokens=token_data.get("output_tokens", 0),
                total_tokens=token_data.get("total_tokens", 0),
                estimated_cost_usd=token_data.get("cost_usd", 0.0),
            ),
            steps=steps,
            message=final_result.get("message", "Completed")
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
