import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Optional, Literal
from app.config import settings


@dataclass
class SandboxResult:
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool
    sandbox_mode: Literal["docker", "local_sandbox"]
    error_message: Optional[str] = None


_DOCKER_CHECKED = False
_DOCKER_AVAILABLE = False


def is_docker_available() -> bool:
    """Checks if Docker engine daemon is responsive (cached)."""
    global _DOCKER_CHECKED, _DOCKER_AVAILABLE
    if _DOCKER_CHECKED:
        return _DOCKER_AVAILABLE

    if not settings.USE_DOCKER_SANDBOX:
        _DOCKER_CHECKED = True
        _DOCKER_AVAILABLE = False
        return False

    try:
        res = subprocess.run(
            ["docker", "ps"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1.5
        )
        _DOCKER_AVAILABLE = (res.returncode == 0)
    except Exception:
        _DOCKER_AVAILABLE = False

    _DOCKER_CHECKED = True
    return _DOCKER_AVAILABLE


def is_docker_image_available(image: str) -> bool:
    """Return whether a sandbox image is already cached locally."""
    if not is_docker_available():
        return False
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1.5,
        )
        return result.returncode == 0
    except Exception:
        return False


def docker_image_for_language(language: str) -> Optional[str]:
    return {
        "python": "python:3.12-alpine",
        "javascript": "node:22-alpine",
        "typescript": "node:22-alpine",
        "c": "gcc:14-bookworm",
        "java": "eclipse-temurin:21-jdk",
    }.get(language)


def normalize_sandbox_language(language: str, filename: Optional[str] = None) -> str:
    """Resolve the actual runtime language from both the label and the filename."""
    if filename:
        lower_name = filename.lower()
        if lower_name.endswith((".ts", ".tsx", ".d.ts", ".cts", ".mts")):
            return "typescript"
        if lower_name.endswith((".js", ".jsx", ".mjs", ".cjs")):
            return "javascript"
        if lower_name.endswith((".c", ".h")):
            return "c"
        if lower_name.endswith(".java"):
            return "java"

    if language is None:
        return "python"

    normalized = language.strip().lower()
    if normalized in ("typescript", "ts"):
        return "typescript"
    if normalized in ("javascript", "js", "node", "nodejs"):
        return "javascript"
    if normalized in ("python", "py"):
        return "python"
    if normalized in ("c", "c11", "c17"):
        return "c"
    if normalized in ("java", "jdk"):
        return "java"
    return normalized


def resolve_sandbox_files(language: str, filename: Optional[str] = None) -> tuple[str, str]:
    """Return the code filename and test filename for the chosen language."""
    runtime_lang = normalize_sandbox_language(language, filename)
    if runtime_lang == "python":
        return "solution.py", "test_solution.py"
    if runtime_lang == "typescript":
        return "solution.ts", "test_solution.ts"
    if runtime_lang == "c":
        return "solution.c", "test_solution.c"
    if runtime_lang == "java":
        return (os.path.basename(filename) if filename and filename.lower().endswith(".java") else "Solution.java"), "TestSolution.java"
    return "solution.js", "test_solution.js"


def normalize_typescript_test_code(test_code: str) -> str:
    """Make local TypeScript imports explicit for Node's native TS runner."""
    cleaned = test_code.strip()
    if not cleaned:
        return cleaned
    return cleaned.replace("'./solution'", "'./solution.ts'").replace('"./solution"', '"./solution.ts"')


def is_declaration_file(filename: Optional[str]) -> bool:
    return bool(filename and filename.lower().endswith(".d.ts"))


def run_declaration_local_sandbox(code: str, timeout: int = 10) -> SandboxResult:
    """Validate a declaration file without trying to execute type-only syntax."""
    start_time = time.time()
    errors = []
    if "\x00" in code:
        errors.append("Declaration file contains a null character")
    if re.search(r"\bdeclar\b", code):
        errors.append("Unknown declaration keyword 'declar'; expected 'declare'")
    if code.count("{") != code.count("}"):
        errors.append("Unbalanced braces in declaration file")
    if re.search(r"\b(?:function|class)\s+\w+\s*\([^)]*\)\s*\{", code):
        errors.append("Declaration files cannot contain function or class implementations")

    duration = round((time.time() - start_time) * 1000, 2)
    return SandboxResult(
        passed=not errors,
        exit_code=0 if not errors else 1,
        stdout="",
        stderr="\n".join(errors),
        duration_ms=duration,
        timed_out=False,
        sandbox_mode="local_sandbox",
        error_message=None if not errors else "Declaration validation failed",
    )


def run_python_local_sandbox(code: str, test_code: str, timeout: int = 10) -> SandboxResult:
    """Runs Python code + tests inside an isolated local temporary directory with strict timeout."""
    temp_dir = tempfile.mkdtemp(prefix="agent_sandbox_py_")
    start_time = time.time()
    try:
        code_file = os.path.join(temp_dir, "solution.py")
        with open(code_file, "w", encoding="utf-8") as f:
            f.write(code)

        test_file = os.path.join(temp_dir, "test_solution.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_code)

        # Create a lightweight standalone runner script to handle both pytest & pure assert tests
        runner_file = os.path.join(temp_dir, "_runner.py")
        runner_content = """import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import pytest
    code = pytest.main(["test_solution.py", "-v", "--tb=short"])
    sys.exit(code)
except ImportError:
    # Fallback to unittest or script execution
    import unittest
    try:
        suite = unittest.defaultTestLoader.discover(os.path.dirname(__file__), pattern="test_*.py")
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
    except Exception as e:
        # Direct execution of test script
        with open("test_solution.py") as f:
            exec(f.read(), {})
        sys.exit(0)
"""
        with open(runner_file, "w", encoding="utf-8") as f:
            f.write(runner_content)

        cmd = [sys.executable, "_runner.py"]
        env = os.environ.copy()
        env["PYTHONPATH"] = temp_dir

        process = subprocess.run(
            cmd,
            cwd=temp_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        duration = round((time.time() - start_time) * 1000, 2)
        passed = (process.returncode == 0)

        return SandboxResult(
            passed=passed,
            exit_code=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
            duration_ms=duration,
            timed_out=False,
            sandbox_mode="local_sandbox",
        )

    except subprocess.TimeoutExpired:
        duration = round((time.time() - start_time) * 1000, 2)
        return SandboxResult(
            passed=False,
            exit_code=-1,
            stdout="",
            stderr=f"Execution timed out after {timeout} seconds",
            duration_ms=duration,
            timed_out=True,
            sandbox_mode="local_sandbox",
            error_message="Execution timeout exceeded"
        )
    except Exception as e:
        duration = round((time.time() - start_time) * 1000, 2)
        return SandboxResult(
            passed=False,
            exit_code=1,
            stdout="",
            stderr=str(e),
            duration_ms=duration,
            timed_out=False,
            sandbox_mode="local_sandbox",
            error_message=str(e)
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_javascript_local_sandbox(code: str, test_code: str, timeout: int = 10) -> SandboxResult:
    """Runs JavaScript code + tests inside an isolated temporary directory with Node test runner."""
    temp_dir = tempfile.mkdtemp(prefix="agent_sandbox_js_")
    start_time = time.time()
    try:
        code_file = os.path.join(temp_dir, "solution.js")
        with open(code_file, "w", encoding="utf-8") as f:
            f.write(code)

        test_file = os.path.join(temp_dir, "test_solution.js")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_code)

        cmd = ["node", "--test", "test_solution.js"]
        process = subprocess.run(
            cmd,
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        duration = round((time.time() - start_time) * 1000, 2)
        passed = (process.returncode == 0)

        return SandboxResult(
            passed=passed,
            exit_code=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
            duration_ms=duration,
            timed_out=False,
            sandbox_mode="local_sandbox",
        )

    except subprocess.TimeoutExpired:
        duration = round((time.time() - start_time) * 1000, 2)
        return SandboxResult(
            passed=False,
            exit_code=-1,
            stdout="",
            stderr=f"Execution timed out after {timeout} seconds",
            duration_ms=duration,
            timed_out=True,
            sandbox_mode="local_sandbox",
            error_message="Execution timeout exceeded"
        )
    except Exception as e:
        duration = round((time.time() - start_time) * 1000, 2)
        return SandboxResult(
            passed=False,
            exit_code=1,
            stdout="",
            stderr=str(e),
            duration_ms=duration,
            timed_out=False,
            sandbox_mode="local_sandbox",
            error_message=str(e)
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_typescript_local_sandbox(code: str, test_code: str, timeout: int = 10) -> SandboxResult:
    """Runs TypeScript code + tests inside an isolated temporary directory using ts-node.
    Requires ts-node to be installed in the environment (e.g., via `npm install -D ts-node`)."""
    temp_dir = tempfile.mkdtemp(prefix="agent_sandbox_ts_")
    start_time = time.time()
    try:
        code_file = os.path.join(temp_dir, "solution.ts")
        with open(code_file, "w", encoding="utf-8") as f:
            f.write(code)

        test_file = os.path.join(temp_dir, "test_solution.ts")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(normalize_typescript_test_code(test_code))

        cmd = ["node", "--experimental-strip-types", "--test", "test_solution.ts"]
        process = subprocess.run(
            cmd,
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        duration = round((time.time() - start_time) * 1000, 2)
        passed = (process.returncode == 0)
        return SandboxResult(
            passed=passed,
            exit_code=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
            duration_ms=duration,
            timed_out=False,
            sandbox_mode="local_sandbox",
        )
    except subprocess.TimeoutExpired:
        duration = round((time.time() - start_time) * 1000, 2)
        return SandboxResult(
            passed=False,
            exit_code=-1,
            stdout="",
            stderr=f"Execution timed out after {timeout} seconds",
            duration_ms=duration,
            timed_out=True,
            sandbox_mode="local_sandbox",
            error_message="Execution timeout exceeded",
        )
    except Exception as e:
        duration = round((time.time() - start_time) * 1000, 2)
        return SandboxResult(
            passed=False,
            exit_code=1,
            stdout="",
            stderr=str(e),
            duration_ms=duration,
            timed_out=False,
            sandbox_mode="local_sandbox",
            error_message=str(e),
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_c_local_sandbox(code: str, test_code: str, timeout: int = 10) -> SandboxResult:
    """Compiles a C solution and harness separately, then runs the linked test binary."""
    temp_dir = tempfile.mkdtemp(prefix="agent_sandbox_c_")
    start_time = time.time()
    try:
        compiler = shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            return SandboxResult(
                passed=False, exit_code=127, stdout="", stderr="No C compiler (gcc or clang) is available",
                duration_ms=round((time.time() - start_time) * 1000, 2), timed_out=False,
                sandbox_mode="local_sandbox", error_message="C compiler unavailable",
            )

        code_file = os.path.join(temp_dir, "solution.c")
        test_file = os.path.join(temp_dir, "test_solution.c")
        solution_object = os.path.join(temp_dir, "solution.o")
        test_object = os.path.join(temp_dir, "test_solution.o")
        executable = os.path.join(temp_dir, "sandbox_test.exe" if os.name == "nt" else "sandbox_test")
        with open(code_file, "w", encoding="utf-8") as file:
            file.write(code)
        with open(test_file, "w", encoding="utf-8") as file:
            file.write(test_code)

        compile_solution = subprocess.run(
            [compiler, "-std=c11", "-Dmain=solution_main", "-c", code_file, "-o", solution_object],
            capture_output=True, text=True, timeout=timeout,
        )
        if compile_solution.returncode != 0:
            return SandboxResult(
                passed=False, exit_code=compile_solution.returncode, stdout=compile_solution.stdout,
                stderr=compile_solution.stderr, duration_ms=round((time.time() - start_time) * 1000, 2),
                timed_out=False, sandbox_mode="local_sandbox",
            )

        compile_test = subprocess.run(
            [compiler, "-std=c11", "-c", test_file, "-o", test_object],
            capture_output=True, text=True, timeout=timeout,
        )
        if compile_test.returncode != 0:
            return SandboxResult(
                passed=False, exit_code=compile_test.returncode, stdout=compile_test.stdout,
                stderr=compile_test.stderr, duration_ms=round((time.time() - start_time) * 1000, 2),
                timed_out=False, sandbox_mode="local_sandbox",
            )

        link = subprocess.run(
            [compiler, solution_object, test_object, "-o", executable],
            capture_output=True, text=True, timeout=timeout,
        )
        if link.returncode != 0:
            return SandboxResult(
                passed=False, exit_code=link.returncode, stdout=link.stdout, stderr=link.stderr,
                duration_ms=round((time.time() - start_time) * 1000, 2), timed_out=False,
                sandbox_mode="local_sandbox",
            )

        process = subprocess.run([executable], cwd=temp_dir, capture_output=True, text=True, timeout=timeout)
        return SandboxResult(
            passed=process.returncode == 0, exit_code=process.returncode, stdout=process.stdout,
            stderr=process.stderr, duration_ms=round((time.time() - start_time) * 1000, 2),
            timed_out=False, sandbox_mode="local_sandbox",
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(
            passed=False, exit_code=-1, stdout="", stderr=f"Execution timed out after {timeout} seconds",
            duration_ms=round((time.time() - start_time) * 1000, 2), timed_out=True,
            sandbox_mode="local_sandbox", error_message="Execution timeout exceeded",
        )
    except Exception as error:
        return SandboxResult(
            passed=False, exit_code=1, stdout="", stderr=str(error),
            duration_ms=round((time.time() - start_time) * 1000, 2), timed_out=False,
            sandbox_mode="local_sandbox", error_message=str(error),
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_java_local_sandbox(code: str, test_code: str, timeout: int = 10, filename: Optional[str] = None) -> SandboxResult:
    """Compiles a Java source file and a plain-main test harness, then runs the harness."""
    temp_dir = tempfile.mkdtemp(prefix="agent_sandbox_java_")
    start_time = time.time()
    try:
        javac = shutil.which("javac")
        java = shutil.which("java")
        if not javac or not java:
            return SandboxResult(
                passed=False, exit_code=127, stdout="", stderr="Java runtime (javac and java) is unavailable",
                duration_ms=round((time.time() - start_time) * 1000, 2), timed_out=False,
                sandbox_mode="local_sandbox", error_message="Java runtime unavailable",
            )

        code_filename = os.path.basename(filename) if filename and filename.lower().endswith(".java") else "Solution.java"
        code_file = os.path.join(temp_dir, code_filename)
        test_file = os.path.join(temp_dir, "TestSolution.java")
        with open(code_file, "w", encoding="utf-8") as file:
            file.write(code)
        with open(test_file, "w", encoding="utf-8") as file:
            file.write(test_code)

        compile_result = subprocess.run(
            [javac, "-d", temp_dir, code_file, test_file],
            cwd=temp_dir, capture_output=True, text=True, timeout=timeout,
        )
        if compile_result.returncode != 0:
            return SandboxResult(
                passed=False, exit_code=compile_result.returncode, stdout=compile_result.stdout,
                stderr=compile_result.stderr, duration_ms=round((time.time() - start_time) * 1000, 2),
                timed_out=False, sandbox_mode="local_sandbox",
            )

        process = subprocess.run(
            [java, "-cp", temp_dir, "TestSolution"],
            cwd=temp_dir, capture_output=True, text=True, timeout=timeout,
        )
        return SandboxResult(
            passed=process.returncode == 0, exit_code=process.returncode, stdout=process.stdout,
            stderr=process.stderr, duration_ms=round((time.time() - start_time) * 1000, 2),
            timed_out=False, sandbox_mode="local_sandbox",
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(
            passed=False, exit_code=-1, stdout="", stderr=f"Execution timed out after {timeout} seconds",
            duration_ms=round((time.time() - start_time) * 1000, 2), timed_out=True,
            sandbox_mode="local_sandbox", error_message="Execution timeout exceeded",
        )
    except Exception as error:
        return SandboxResult(
            passed=False, exit_code=1, stdout="", stderr=str(error),
            duration_ms=round((time.time() - start_time) * 1000, 2), timed_out=False,
            sandbox_mode="local_sandbox", error_message=str(error),
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_docker_sandbox(
    code: str,
    test_code: str,
    language: str,
    timeout: int = 10,
    filename: Optional[str] = None,
) -> SandboxResult:
    """
    Executes code and tests inside an ephemeral, resource-constrained, network-isolated Docker container.
    """
    temp_dir = tempfile.mkdtemp(prefix="agent_docker_sandbox_")
    start_time = time.time()
    try:
        resolved_language = normalize_sandbox_language(language, filename)
        is_python = resolved_language == "python"
        code_filename, test_filename = resolve_sandbox_files(resolved_language, filename)

        with open(os.path.join(temp_dir, code_filename), "w", encoding="utf-8") as f:
            f.write(code)
        with open(os.path.join(temp_dir, test_filename), "w", encoding="utf-8") as f:
            f.write(
                normalize_typescript_test_code(test_code)
                if resolved_language == "typescript"
                else test_code
            )

        image_by_language = {
            "python": "python:3.12-alpine",
            "javascript": "node:22-alpine",
            "typescript": "node:22-alpine",
            "c": "gcc:14-bookworm",
            "java": "eclipse-temurin:21-jdk",
        }
        command_by_language = {
            "python": "python -m unittest test_solution.py -v",
            "javascript": "node --test test_solution.js",
            "typescript": "node --experimental-strip-types --test test_solution.ts",
            "c": "gcc -std=c11 -Dmain=solution_main -c solution.c -o solution.o && gcc -std=c11 -c test_solution.c -o test_solution.o && gcc solution.o test_solution.o -o sandbox_test && ./sandbox_test",
            "java": "javac -d . *.java && java TestSolution",
        }
        image = image_by_language[resolved_language]
        test_cmd = command_by_language[resolved_language]

        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", settings.SANDBOX_MEMORY_LIMIT,
            "--cpus", "1.0",
            "-v", f"{temp_dir}:/sandbox",
            "-w", "/sandbox",
            image,
            "sh", "-c", test_cmd
        ]

        process = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        duration = round((time.time() - start_time) * 1000, 2)
        passed = (process.returncode == 0)

        return SandboxResult(
            passed=passed,
            exit_code=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
            duration_ms=duration,
            timed_out=False,
            sandbox_mode="docker",
        )

    except subprocess.TimeoutExpired:
        duration = round((time.time() - start_time) * 1000, 2)
        return SandboxResult(
            passed=False,
            exit_code=-1,
            stdout="",
            stderr=f"Docker sandbox timed out after {timeout}s",
            duration_ms=duration,
            timed_out=True,
            sandbox_mode="docker",
            error_message="Sandbox timeout exceeded"
        )
    except Exception:
        # Fall back to local isolated runner
        if resolved_language == "python":
            return run_python_local_sandbox(code, test_code, timeout=timeout)
        if resolved_language == "javascript":
            return run_javascript_local_sandbox(code, test_code, timeout=timeout)
        if resolved_language == "typescript":
            return run_typescript_local_sandbox(code, test_code, timeout=timeout)
        if resolved_language == "c":
            return run_c_local_sandbox(code, test_code, timeout=timeout)
        if resolved_language == "java":
            return run_java_local_sandbox(code, test_code, timeout=timeout, filename=filename)
        raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def execute_in_sandbox(
    code: str,
    test_code: str,
    language: str,
    timeout: int = 10,
    filename: Optional[str] = None,
) -> SandboxResult:
    """
    Unified entry point for sandbox execution.
    Executes in local isolated sandbox or Docker sandbox with strict timeout and resource safety.
    """
    resolved_language = normalize_sandbox_language(language, filename)

    if resolved_language == "typescript" and is_declaration_file(filename):
        return run_declaration_local_sandbox(code, timeout=timeout)

    # Prefer the language-specific Docker images when Docker is available. The
    # C and Java images provide their compilers even when the host does not.
    docker_image = docker_image_for_language(resolved_language)
    if docker_image and is_docker_image_available(docker_image):
        return run_docker_sandbox(
            code=code,
            test_code=test_code,
            language=resolved_language,
            timeout=timeout,
            filename=filename,
        )

    if resolved_language == "python":
        return run_python_local_sandbox(code, test_code, timeout=timeout)
    elif resolved_language == "javascript":
        return run_javascript_local_sandbox(code, test_code, timeout=timeout)
    elif resolved_language == "typescript":
        return run_typescript_local_sandbox(code, test_code, timeout=timeout)
    elif resolved_language == "c":
        return run_c_local_sandbox(code, test_code, timeout=timeout)
    elif resolved_language == "java":
        return run_java_local_sandbox(code, test_code, timeout=timeout, filename=filename)
    else:
        return SandboxResult(
            passed=False,
            exit_code=1,
            stdout="",
            stderr=f"Unsupported sandbox language: {language}",
            duration_ms=0,
            timed_out=False,
            sandbox_mode="local_sandbox",
            error_message=f"Unsupported language {language}"
        )
