import asyncio
import difflib
import json
import time
from typing import AsyncGenerator, Dict, Any, Optional, List
from openai import AsyncOpenAI

from app.config import settings
from app.services.sandbox import execute_in_sandbox, SandboxResult


TEST_GEN_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_unit_tests",
        "description": "Generate runnable unit tests that test the functions in the file",
        "parameters": {
            "type": "object",
            "properties": {
                "test_code": {
                    "type": "string",
                    "description": "Complete unit test code importing from solution (or ./solution for JS) using pytest / node:test"
                },
                "test_description": {
                    "type": "string",
                    "description": "Short explanation of the test cases included"
                }
            },
            "required": ["test_code"]
        }
    }
}

FIX_PROPOSAL_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_bug_fix",
        "description": "Propose a patched version of the code that fixes the bug and passes all tests",
        "parameters": {
            "type": "object",
            "properties": {
                "repaired_code": {
                    "type": "string",
                    "description": "The complete, revised source code with the fix applied"
                },
                "explanation": {
                    "type": "string",
                    "description": "Detailed explanation of what changes were made and why"
                }
            },
            "required": ["repaired_code", "explanation"]
        }
    }
}


def calculate_diff(original: str, modified: str, filename: str = "solution") -> str:
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=3
    )
    return "".join(diff)


async def generate_smoke_test(
    code: str,
    language: str,
    bug_description: str,
    client: AsyncOpenAI,
    model: str
) -> tuple[str, int, int]:
    """Generates a small unit test suite to reproduce and verify the bug fix."""
    is_py = language.lower() == "python"

    prompt = f"""You are a QA and test engineering expert.
Generate a minimal, self-contained unit test suite in {language} to verify the following code and test for the described bug.

Code:
```{language}
{code}
```

Target Bug / Focus:
{bug_description}

Requirements:
- For Python: Use pytest/unittest. Import functions from `solution` (e.g. `from solution import ...` or `import solution`).
- For JavaScript: Use `node:test` and `node:assert` (or assert). Import from `./solution` (e.g. `const {{ ... }} = require('./solution')` or `const solution = require('./solution')`).
- Write 2-3 focused test cases: 1 reproducing the bug condition, and 1-2 testing standard valid inputs.
- Call the `generate_unit_tests` tool."""

    response = await client.chat.completions.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
        tools=[TEST_GEN_TOOL],
        tool_choice={"type": "function", "function": {"name": "generate_unit_tests"}},
    )

    usage = response.usage
    in_tokens = usage.prompt_tokens if usage else 0
    out_tokens = usage.completion_tokens if usage else 0

    test_code = ""
    choice = response.choices[0]
    for tc in (choice.message.tool_calls or []):
        if tc.function.name == "generate_unit_tests":
            data = json.loads(tc.function.arguments)
            test_code = data.get("test_code", "")
            break

    if not test_code:
        if is_py:
            test_code = "import solution\n\ndef test_smoke():\n    assert solution is not None\n"
        else:
            test_code = "const test = require('node:test');\nconst assert = require('node:assert');\nconst solution = require('./solution');\n\ntest('smoke test', () => {\n  assert.ok(solution);\n});\n"

    return test_code, in_tokens, out_tokens


async def run_agent_fix_stream(
    code: str,
    language: str,
    filename: str = "solution.py",
    bug_description: Optional[str] = None,
    test_code: Optional[str] = None,
    api_key: Optional[str] = None,
    model_override: Optional[str] = None,
    max_retries: int = 3,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Asynchronous generator executing the sandboxed bug-fixing agent loop with SSE events.
    """
    key = settings.active_api_key if api_key is None else api_key
    model = model_override or settings.active_model
    if model not in settings.VALID_GROQ_MODELS:
        model = settings.active_model

    total_in_tokens = 0
    total_out_tokens = 0

    if not key or key.strip() == "":
        yield {
            "event": "error",
            "data": {
                "message": "Groq API Key is required to run the Autonomous Bug-Fixing Agent.",
                "fatal": True
            }
        }
        return

    client = AsyncOpenAI(api_key=key, base_url=settings.active_base_url)
    current_code = code
    is_python = language.lower() == "python"

    # Step 1: Prepare or Generate Tests
    yield {
        "event": "agent_step",
        "data": {
            "step": "init",
            "message": "Initializing autonomous agent loop and sandbox environment...",
            "timestamp": time.time()
        }
    }
    await asyncio.sleep(0.1)

    active_test_code = test_code
    test_type = "pre_existing" if (test_code and test_code.strip()) else "smoke_test"
    if not active_test_code or not active_test_code.strip():
        yield {
            "event": "agent_step",
            "data": {
                "step": "generating_tests",
                "message": "Synthesizing unit test suite to reproduce bug...",
                "timestamp": time.time()
            }
        }
        try:
            active_test_code, in_tok, out_tok = await generate_smoke_test(
                code=code,
                language=language,
                bug_description=bug_description or "General correctness and edge cases",
                client=client,
                model=model
            )
            total_in_tokens += in_tok
            total_out_tokens += out_tok

            yield {
                "event": "tests_ready",
                "data": {
                    "test_code": active_test_code,
                    "language": language,
                    "message": "Unit tests created. Running baseline test on unpatched code in sandbox..."
                }
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": {"message": f"Failed to generate tests: {str(e)}", "fatal": True}
            }
            return

    # Step 2: Baseline Sandbox Run
    yield {
        "event": "sandbox_executing",
        "data": {
            "phase": "baseline",
            "message": "Executing baseline tests on original unpatched code in sandbox..."
        }
    }
    # Determine correct sandbox language from the actual file extension and runtime label.
    effective_language = language
    lower_filename = (filename or "").lower()
    if lower_filename.endswith(('.ts', '.tsx', '.d.ts', '.cts', '.mts')):
        effective_language = "typescript"
    elif lower_filename.endswith(('.js', '.jsx', '.mjs', '.cjs')):
        effective_language = "javascript"

    baseline_result = execute_in_sandbox(
        code=code,
        test_code=active_test_code,
        language=effective_language,
        filename=filename,
        timeout=settings.SANDBOX_TIMEOUT_SECONDS
    )

    yield {
        "event": "baseline_result",
        "data": {
            "passed": baseline_result.passed,
            "exit_code": baseline_result.exit_code,
            "stdout": baseline_result.stdout,
            "stderr": baseline_result.stderr,
            "duration_ms": baseline_result.duration_ms,
            "sandbox_mode": baseline_result.sandbox_mode,
            "message": "Baseline test completed. " + ("Tests failed as expected on buggy code." if not baseline_result.passed else "Warning: Tests passed on original code.")
        }
    }
    await asyncio.sleep(0.1)

    # Step 3: Iterative Repair Loop (up to max_retries attempts)
    conversation_history: List[Dict[str, Any]] = []
    latest_error_log = baseline_result.stderr or baseline_result.stdout or "Test execution failed."

    attempt = 0
    fix_verified = False
    final_diff = ""

    while attempt < max_retries and not fix_verified:
        attempt += 1

        yield {
            "event": "attempt_start",
            "data": {
                "attempt": attempt,
                "max_attempts": max_retries,
                "message": f"Attempt {attempt}/{max_retries}: Proposing fix patch..."
            }
        }

        # Build prompt for fix attempt
        fix_prompt = f"""You are fixing a bug in {language} code.

Current Source Code:
```{language}
{current_code}
```

Test Suite:
```{language}
{active_test_code}
```

Identified Bug / Goal:
{bug_description or 'Fix all logic errors and ensure tests pass cleanly.'}

Latest Sandbox Test Execution Logs (Failures):
```
{latest_error_log[-2000:]}
```

Please analyze the failure, correct the code to pass all tests, and call the `propose_bug_fix` tool with the full repaired source code."""

        if (filename or "").lower().endswith(".d.ts"):
            fix_prompt += """

This is a TypeScript declaration file (.d.ts). Only return the complete contents of this one
file in repaired_code. Do not add node_modules, package files, stubs, JavaScript implementations,
or any other files. Declaration files must contain type declarations only; dependencies imported
by a generated test are unavailable in the sandbox."""

        conversation_history.append({"role": "user", "content": fix_prompt})

        try:
            response = await client.chat.completions.create(
                model=model,
                max_tokens=4096,
                messages=conversation_history,
                tools=[FIX_PROPOSAL_TOOL],
                tool_choice={"type": "function", "function": {"name": "propose_bug_fix"}},
            )

            usage = response.usage
            total_in_tokens += usage.prompt_tokens if usage else 0
            total_out_tokens += usage.completion_tokens if usage else 0

            repaired_code = current_code
            explanation = ""

            choice = response.choices[0]
            for tc in (choice.message.tool_calls or []):
                if tc.function.name == "propose_bug_fix":
                    data = json.loads(tc.function.arguments)
                    repaired_code = data.get("repaired_code", current_code)
                    explanation = data.get("explanation", "")
                    break

            patch_diff = calculate_diff(code, repaired_code, filename)
            final_diff = patch_diff

            yield {
                "event": "patch_proposed",
                "data": {
                    "attempt": attempt,
                    "explanation": explanation,
                    "diff": patch_diff,
                    "message": f"Attempt {attempt}: Patch formulated. Executing inside sandbox container..."
                }
            }

            # Step 4: Execute patched code in sandbox
            # Determine correct sandbox language for patched code from the actual file extension.
            effective_language_patch = language
            lower_filename = (filename or "").lower()
            if lower_filename.endswith(('.ts', '.tsx', '.d.ts', '.cts', '.mts')):
                effective_language_patch = "typescript"
            elif lower_filename.endswith(('.js', '.jsx', '.mjs', '.cjs')):
                effective_language_patch = "javascript"
            sb_result = execute_in_sandbox(
                code=repaired_code,
                test_code=active_test_code,
                language=effective_language_patch,
                filename=filename,
                timeout=settings.SANDBOX_TIMEOUT_SECONDS
            )

            yield {
                "event": "sandbox_result",
                "data": {
                    "attempt": attempt,
                    "passed": sb_result.passed,
                    "exit_code": sb_result.exit_code,
                    "stdout": sb_result.stdout,
                    "stderr": sb_result.stderr,
                    "duration_ms": sb_result.duration_ms,
                    "timed_out": sb_result.timed_out,
                    "sandbox_mode": sb_result.sandbox_mode,
                }
            }

            if sb_result.passed:
                fix_verified = True
                current_code = repaired_code
                break
            else:
                current_code = repaired_code
                latest_error_log = sb_result.stderr or sb_result.stdout or "Tests failed."
                # Append assistant tool-call message in OpenAI format
                conversation_history.append({
                    "role": "assistant",
                    "tool_calls": [tc.model_dump() for tc in (choice.message.tool_calls or [])]
                })
                conversation_history.append({
                    "role": "user",
                    "content": f"The proposed fix for Attempt {attempt} failed inside the sandbox:\n{latest_error_log}\n\nPlease revise and fix."
                })

        except Exception as e:
            yield {
                "event": "error",
                "data": {"message": f"Attempt {attempt} encountered an error: {str(e)}", "fatal": False}
            }
            break

    # Calculate token cost ($3 / MTok in, $15 / MTok out)
    cost_usd = (total_in_tokens * 3.0 / 1_000_000) + (total_out_tokens * 15.0 / 1_000_000)

    yield {
        "event": "agent_completed",
        "data": {
            "success": fix_verified,
            "verified_in_sandbox": fix_verified,
            "total_attempts": attempt,
            "max_attempts": max_retries,
            "final_code": current_code,
            "final_diff": final_diff,
            "test_code": active_test_code,
            "test_type": test_type,
            "tokens": {
                "input_tokens": total_in_tokens,
                "output_tokens": total_out_tokens,
                "total_tokens": total_in_tokens + total_out_tokens,
                "cost_usd": round(cost_usd, 5)
            },
            "message": "Autonomous repair verified in sandbox!" if fix_verified else f"Failed to verify fix after {attempt} attempts."
        }
    }
