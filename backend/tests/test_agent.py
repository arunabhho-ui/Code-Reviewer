import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.sandbox import execute_in_sandbox, resolve_sandbox_files, run_python_local_sandbox, run_javascript_local_sandbox


@pytest.mark.parametrize("language, expected_code, expected_test", [
    ("python", "solution.py", "test_solution.py"),
    ("javascript", "solution.js", "test_solution.js"),
    ("typescript", "solution.ts", "test_solution.ts"),
    ("c", "solution.c", "test_solution.c"),
    ("java", "Solution.java", "TestSolution.java"),
])
def test_sandbox_uses_language_specific_test_filename(language, expected_code, expected_test):
    assert resolve_sandbox_files(language) == (expected_code, expected_test)


def test_python_sandbox_passing_test():
    code = "def multiply(a: int, b: int) -> int:\n    return a * b\n"
    test_code = "from solution import multiply\n\ndef test_mult():\n    assert multiply(3, 4) == 12\n"
    result = execute_in_sandbox(code, test_code, "python", timeout=5)
    assert result.passed is True
    assert result.exit_code == 0
    assert result.timed_out is False


def test_python_sandbox_failing_test():
    buggy_code = "def multiply(a: int, b: int) -> int:\n    return a + b\n"
    test_code = "from solution import multiply\n\ndef test_mult():\n    assert multiply(3, 4) == 12\n"
    result = execute_in_sandbox(buggy_code, test_code, "python", timeout=5)
    assert result.passed is False
    assert result.exit_code != 0


def test_python_sandbox_timeout():
    infinite_loop = "import time\ndef hang():\n    time.sleep(10)\n"
    test_code = "from solution import hang\ndef test_hang():\n    hang()\n"
    result = execute_in_sandbox(infinite_loop, test_code, "python", timeout=2)
    assert result.passed is False
    assert result.timed_out is True


def test_js_sandbox_passing_test():
    js_code = "function add(a, b) {\n    return a + b;\n}\nmodule.exports = { add };\n"
    js_test = "const test = require('node:test');\nconst assert = require('node:assert');\nconst { add } = require('./solution');\n\ntest('adds numbers', () => {\n    assert.strictEqual(add(2, 3), 5);\n});\n"
    result = execute_in_sandbox(js_code, js_test, "javascript", timeout=5)
    assert result.passed is True
    assert result.exit_code == 0


def test_typescript_sandbox_accepts_ts_filename_even_when_language_is_js_label():
    ts_code = "export function add(a: number, b: number): number {\n    return a + b;\n}\n"
    ts_test = "import test from 'node:test';\nimport assert from 'node:assert/strict';\nimport { add } from './solution';\n\ntest('adds numbers', () => {\n    assert.equal(add(2, 3), 5);\n});\n"
    result = execute_in_sandbox(ts_code, ts_test, "javascript", timeout=10, filename='solution.ts')
    assert result.passed is True
    assert result.exit_code == 0


def test_declaration_sandbox_validates_d_ts_without_executing_generated_imports():
    buggy_code = 'declar module "*.css" {\n  const content: Record<string, string>;\n  export default content;\n}\n'
    fixed_code = 'declare module "*.css" {\n  const content: Record<string, string>;\n  export default content;\n}\n'

    failed = execute_in_sandbox(buggy_code, "import typescript from 'typescript';", "typescript", filename="app.d.ts")
    passed = execute_in_sandbox(fixed_code, "import typescript from 'typescript';", "typescript", filename="app.d.ts")

    assert failed.passed is False
    assert passed.passed is True


def test_c_sandbox_reports_compiler_status():
    code = "int add(int a, int b) { return a + b; }\n"
    test_code = "#include <assert.h>\nint add(int, int);\nint main(void) { assert(add(2, 3) == 5); return 0; }\n"
    result = execute_in_sandbox(code, test_code, "c", timeout=10)
    assert result.sandbox_mode in ("local_sandbox", "docker")
    assert "Unsupported sandbox language" not in result.stderr
    if result.error_message != "C compiler unavailable":
        assert result.passed is True


def test_java_sandbox_runs_plain_main_test():
    code = "public class Calculator { public static int add(int a, int b) { return a + b; } }\n"
    test_code = "class TestSolution { public static void main(String[] args) { if (Calculator.add(2, 3) != 5) throw new AssertionError(); } }\n"
    result = execute_in_sandbox(code, test_code, "java", timeout=10, filename="Calculator.java")
    assert result.passed is True


@pytest.mark.asyncio
async def test_agent_fix_endpoint_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Calling without API key should gracefully error / report missing key
        payload = {
            "code": "def buggy(): return 1 / 0",
            "language": "python",
            "bug_description": "Zero division error",
            "api_key": ""
        }
        response = await client.post("/api/agent/fix", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "API Key" in data["detail"]
