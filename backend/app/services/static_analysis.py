import ast
import json
import os
import re
import subprocess
import tempfile
from typing import List
from app.models.schemas import StaticFinding, SeverityLevel, IssueCategory


def map_ruff_code_to_category_and_severity(code: str) -> tuple[IssueCategory, SeverityLevel]:
    """Maps Ruff rule codes to standardized categories and severities."""
    code_upper = code.upper()
    if code_upper.startswith("S") or "SECURITY" in code_upper:
        return "security", "high"
    elif code_upper.startswith("F") or code_upper.startswith("B"):
        return "bug", "high" if code_upper.startswith("F821") or code_upper.startswith("F822") else "medium"
    elif code_upper.startswith("PERF") or code_upper.startswith("C4") or code_upper.startswith("PIE"):
        return "performance", "medium"
    elif code_upper.startswith("E") or code_upper.startswith("W") or code_upper.startswith("I") or code_upper.startswith("D"):
        return "style", "low"
    return "bug", "medium"


def analyze_python_with_ast(code: str, filename: str = "snippet.py") -> List[StaticFinding]:
    """Fallback AST parser that detects syntax errors and basic anti-patterns in Python."""
    findings: List[StaticFinding] = []
    try:
        tree = ast.parse(code, filename=filename)
    except SyntaxError as e:
        findings.append(
            StaticFinding(
                file=filename,
                line=e.lineno or 1,
                column=e.offset or 0,
                rule="AST-SYNTAX-ERR",
                message=f"Syntax Error: {e.msg}",
                severity="critical",
                category="bug",
            )
        )
        return findings

    # Basic AST checks (e.g., bare except, dangerous eval/exec)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append(
                StaticFinding(
                    file=filename,
                    line=node.lineno,
                    column=node.col_offset,
                    rule="AST-BARE-EXCEPT",
                    message="Avoid bare 'except:' clauses; specify Exception type",
                    severity="medium",
                    category="bug",
                )
            )
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                findings.append(
                    StaticFinding(
                        file=filename,
                        line=node.lineno,
                        column=node.col_offset,
                        rule="AST-DANGEROUS-EVAL",
                        message=f"Use of '{node.func.id}()' can lead to arbitrary code execution",
                        severity="critical",
                        category="security",
                    )
                )
    return findings


def analyze_python_code(code: str, filename: str = "snippet.py") -> List[StaticFinding]:
    """Runs Ruff static analysis on Python code, falling back to AST parser if needed."""
    findings: List[StaticFinding] = []
    
    # 1. AST check for fatal syntax errors
    ast_findings = analyze_python_with_ast(code, filename)
    if any(f.severity == "critical" for f in ast_findings):
        return ast_findings

    # 2. Try Ruff CLI
    temp_dir = tempfile.mkdtemp(prefix="review_static_")
    file_path = os.path.join(temp_dir, os.path.basename(filename) if filename.endswith(".py") else "snippet.py")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        cmd = [
            "python", "-m", "ruff", "check",
            "--select", "E,W,F,B,S,PERF,UP,C4,PIE",
            "--output-format=json",
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        stdout = result.stdout.strip()
        
        if stdout:
            try:
                ruff_items = json.loads(stdout)
                for item in ruff_items:
                    code_rule = item.get("code", "RUFF")
                    cat, sev = map_ruff_code_to_category_and_severity(code_rule)
                    location = item.get("location", {})
                    findings.append(
                        StaticFinding(
                            file=filename,
                            line=location.get("row", 1),
                            column=location.get("column", 0),
                            rule=code_rule,
                            message=item.get("message", "Static check warning"),
                            severity=sev,
                            category=cat,
                        )
                    )
            except json.JSONDecodeError:
                pass
    except Exception:
        pass
    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rmdir(temp_dir)
        except Exception:
            pass

    # If Ruff found nothing or wasn't available, merge AST findings
    if not findings:
        findings = ast_findings
    return findings


def analyze_javascript_code(code: str, filename: str = "snippet.js") -> List[StaticFinding]:
    """Runs deterministic static checks on JavaScript/TypeScript code."""
    findings: List[StaticFinding] = []
    
    # 1. Quick Node syntax test with node -c via temp file
    temp_dir = tempfile.mkdtemp(prefix="review_js_")
    file_path = os.path.join(temp_dir, os.path.basename(filename) if filename.endswith((".js", ".ts", ".jsx", ".tsx")) else "snippet.js")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        result = subprocess.run(["node", "-c", file_path], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            err_line = 1
            stderr = result.stderr
            match = re.search(r":(\d+)", stderr)
            if match:
                err_line = int(match.group(1))
            findings.append(
                StaticFinding(
                    file=filename,
                    line=err_line,
                    column=0,
                    rule="JS-SYNTAX-ERROR",
                    message=f"JavaScript Syntax Error: {stderr.splitlines()[0] if stderr else 'Invalid syntax'}",
                    severity="critical",
                    category="bug",
                )
            )
    except Exception:
        pass
    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rmdir(temp_dir)
        except Exception:
            pass

    # 2. Rule-based static checks for common vulnerabilities and bugs in JS
    lines = code.split("\n")
    for idx, line in enumerate(lines, 1):
        # eval() check
        if re.search(r"\beval\s*\(", line):
            findings.append(
                StaticFinding(
                    file=filename,
                    line=idx,
                    rule="JS-SECURITY-EVAL",
                    message="Use of eval() is a severe security risk and harms engine optimization",
                    severity="critical",
                    category="security",
                )
            )
        # innerHTML assignment check
        if re.search(r"\.innerHTML\s*=", line):
            findings.append(
                StaticFinding(
                    file=filename,
                    line=idx,
                    rule="JS-SECURITY-INNERHTML",
                    message="Direct innerHTML assignment is vulnerable to Cross-Site Scripting (XSS)",
                    severity="high",
                    category="security",
                )
            )
        # Loose equality check == vs ===
        if re.search(r"[^!=]==[^=]", line):
            findings.append(
                StaticFinding(
                    file=filename,
                    line=idx,
                    rule="JS-LOOSE-EQUALITY",
                    message="Use strict equality '===' instead of loose equality '==' to prevent unexpected type coercion",
                    severity="low",
                    category="style",
                )
            )
        # Unhandled promise warning / async without try-catch heuristic
        if "async" in line and "function" in line and "try" not in line:
            # Informational check
            pass

    return findings


def analyze_c_code(code: str, filename: str = "snippet.c") -> List[StaticFinding]:
    """Run compiler syntax checks and flag common unsafe C operations."""
    findings: List[StaticFinding] = []
    lines = code.split("\n")
    for idx, line in enumerate(lines, 1):
        if re.search(r"\bstrcpy\s*\(", line):
            findings.append(StaticFinding(
                file=filename, line=idx, rule="C-UNSAFE-STRCPY",
                message="strcpy() does not enforce the destination buffer size and can overflow it",
                severity="high", category="security",
            ))
        if re.search(r"\bgets\s*\(", line):
            findings.append(StaticFinding(
                file=filename, line=idx, rule="C-UNSAFE-GETS",
                message="gets() cannot limit input length and is unsafe; use fgets() instead",
                severity="critical", category="security",
            ))

    temp_dir = tempfile.mkdtemp(prefix="review_c_")
    file_path = os.path.join(temp_dir, os.path.basename(filename) if filename.endswith((".c", ".h")) else "snippet.c")
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(code)
        result = subprocess.run(["gcc", "-fsyntax-only", file_path], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            findings.append(StaticFinding(
                file=filename, line=1, rule="C-SYNTAX-ERROR",
                message=f"C syntax error: {result.stderr.splitlines()[0] if result.stderr else 'Invalid syntax'}",
                severity="critical", category="bug",
            ))
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rmdir(temp_dir)
        except OSError:
            pass
    return findings


def analyze_java_code(code: str, filename: str = "Snippet.java") -> List[StaticFinding]:
    """Run javac syntax checks and flag resources that should use try-with-resources."""
    findings: List[StaticFinding] = []
    lines = code.split("\n")
    for idx, line in enumerate(lines, 1):
        if re.search(r"\bnew\s+(?:FileReader|FileInputStream|BufferedReader|InputStreamReader)\s*\(", line):
            findings.append(StaticFinding(
                file=filename, line=idx, rule="JAVA-RESOURCE-LEAK",
                message="Close this I/O resource or use try-with-resources to prevent resource leaks",
                severity="medium", category="bug",
            ))

    temp_dir = tempfile.mkdtemp(prefix="review_java_")
    safe_filename = os.path.basename(filename) if filename.endswith(".java") else "Snippet.java"
    file_path = os.path.join(temp_dir, safe_filename)
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(code)
        result = subprocess.run(["javac", "-Xlint:none", "-d", temp_dir, file_path], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            findings.append(StaticFinding(
                file=filename, line=1, rule="JAVA-SYNTAX-ERROR",
                message=f"Java compilation error: {result.stderr.splitlines()[0] if result.stderr else 'Invalid syntax'}",
                severity="critical", category="bug",
            ))
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        try:
            for name in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, name))
            os.rmdir(temp_dir)
        except OSError:
            pass
    return findings


def run_static_analysis(code: str, language: str, filename: str = "snippet") -> List[StaticFinding]:
    """Unified entry point for static analysis."""
    if language.lower() == "python":
        return analyze_python_code(code, filename)
    elif language.lower() in ("javascript", "typescript", "js", "ts"):
        return analyze_javascript_code(code, filename)
    elif language.lower() in ("c", "c++", "cpp"):
        return analyze_c_code(code, filename)
    elif language.lower() == "java":
        return analyze_java_code(code, filename)
    return []
