import ast
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.models.schemas import SeverityLevel


class RulesSecurityHit(BaseModel):
    rule_id: str
    vulnerability_type: str
    file: str
    line: int
    column: Optional[int] = 0
    severity: SeverityLevel
    message: str
    matched_snippet: str
    suggested_fix: Optional[str] = None


# Regex Patterns for Hardcoded Secrets
SECRET_PATTERNS = [
    (
        r"""(?i)(?:api[_-]?key|apikey|secret|token|password|passwd|auth[_-]?token|access[_-]?token|private[_-]?key)\s*[:=]\s*['"]([a-zA-Z0-9_\-\.]{8,})['"]""",
        "HARDCODED-SECRET",
        "Hardcoded Secret / Credential",
        "high",
        "Detected potential hardcoded secret or API key. Store credentials in environment variables.",
        "Use os.environ.get('SECRET_NAME') or a secure secrets manager instead of hardcoding."
    ),
    (
        r"""(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{82}|sk-[a-zA-Z0-9]{32,}|AKIA[0-9A-Z]{16})""",
        "HARDCODED-API-TOKEN",
        "Hardcoded High-Entropy API Token",
        "critical",
        "Detected known API token format (GitHub, OpenAI, or AWS key) hardcoded in source.",
        "Revoke this token immediately and reference it via environment variables."
    ),
    (
        r"""-----BEGIN (?:RSA )?PRIVATE KEY-----""",
        "HARDCODED-PRIVATE-KEY",
        "Hardcoded Cryptographic Private Key",
        "critical",
        "Detected hardcoded private cryptographic key.",
        "Store private keys in a secure vault or file outside repository tracking."
    ),
]

# Regex Patterns for SQL Injection
SQL_INJECTION_PATTERNS = [
    (
        r"""(?i)f['"][^'"]*?(?:SELECT|INSERT|UPDATE|DELETE|DROP|FROM|WHERE)[^'"]*?['"]""",
        "SQLI-FSTRING",
        "SQL Injection via F-String",
        "critical",
        "SQL query constructed using Python f-string interpolation, allowing SQL injection.",
        "Use parameterized queries: cursor.execute('SELECT ... WHERE col = %s', (val,))"
    ),
    (
        r"""(?i)['"][^'"]*?(?:SELECT|INSERT|UPDATE|DELETE|DROP|FROM|WHERE)[^'"]*?['"]\s*%\s*""",
        "SQLI-PERCENT-FORMAT",
        "SQL Injection via %-Formatting",
        "critical",
        "SQL query formatted using % operator rather than parameterized query binding.",
        "Pass arguments as a second tuple/list parameter to cursor.execute()."
    ),
    (
        r"""(?i)['"][^'"]*?(?:SELECT|INSERT|UPDATE|DELETE|DROP|FROM|WHERE)[^'"]*?['"]\.format\s*\(""",
        "SQLI-STR-FORMAT",
        "SQL Injection via .format()",
        "critical",
        "SQL query constructed using .format(), enabling query injection.",
        "Use parameterized query placeholders supported by your database driver."
    ),
    (
        r"""(?i)['"][^'"]*?(?:SELECT|INSERT|UPDATE|DELETE|DROP|FROM|WHERE)[^'"]*?['"]\s*\+""",
        "SQLI-CONCATENATION",
        "SQL Injection via String Concatenation",
        "critical",
        "SQL query constructed using raw string concatenation '+'.",
        "Use parameterized queries with bind variables instead of concatenating strings."
    ),
    (
        r"""(?i)`[^`]*?(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE)[^`]*?\${[^}]+}[^`]*?`""",
        "JS-SQLI-TEMPLATE-LITERAL",
        "SQL Injection via JS Template Literal",
        "critical",
        "SQL query dynamically interpolated with template literals `${...}` in JavaScript.",
        "Use parameterized queries: client.query('SELECT ... WHERE col = $1', [param])"
    ),
]

# Regex Patterns for Command Injection
COMMAND_INJECTION_PATTERNS = [
    (
        r"""os\.system\s*\(""",
        "CMD-INJECTION-OS-SYSTEM",
        "Command Injection Risk via os.system",
        "high",
        "os.system() executes shell commands without argument escaping, vulnerable to injection if input is untrusted.",
        "Use subprocess.run(['cmd', arg], check=True) with a list of arguments and shell=False."
    ),
    (
        r"""subprocess\.(?:run|Popen|call|check_call|check_output)\s*\([^)]*shell\s*=\s*True""",
        "CMD-INJECTION-SHELL-TRUE",
        "Command Injection Risk via shell=True",
        "high",
        "subprocess invoked with shell=True allows arbitrary command execution through metacharacters.",
        "Pass arguments as a list and set shell=False (default)."
    ),
    (
        r"""os\.popen\s*\(""",
        "CMD-INJECTION-OS-POPEN",
        "Command Injection Risk via os.popen",
        "medium",
        "os.popen() passes commands directly to system shell.",
        "Use subprocess.run(..., shell=False)."
    ),
    (
        r"""(?:child_process|cp)\.(?:exec|execSync)\s*\([^)]*\+""",
        "JS-CMD-INJECTION-EXEC",
        "Command Injection via child_process.exec Concatenation",
        "critical",
        "Executing system shell command with concatenated input strings.",
        "Use child_process.execFile() with an array of arguments."
    ),
]

# Regex Patterns for Unsafe Deserialization
DESERIALIZATION_PATTERNS = [
    (
        r"""pickle\.(?:loads|load)\s*\(""",
        "UNSAFE-DESERIALIZATION-PICKLE",
        "Unsafe Deserialization via pickle",
        "critical",
        "pickle deserialization can execute arbitrary code upon unpickling untrusted data.",
        "Use safe serialization formats like JSON, protocol buffers, or hmac verification."
    ),
    (
        r"""yaml\.load\s*\([^)]*(?:Loader\s*=\s*yaml\.(?:UnsafeLoader|Loader)|(?<!SafeLoader)\))""",
        "UNSAFE-YAML-LOAD",
        "Unsafe Deserialization via yaml.load",
        "high",
        "yaml.load without yaml.SafeLoader can instantiate arbitrary Python objects.",
        "Use yaml.safe_load(data) or yaml.load(data, Loader=yaml.SafeLoader)."
    ),
    (
        r"""marshal\.loads\s*\(""",
        "UNSAFE-DESERIALIZATION-MARSHAL",
        "Unsafe Deserialization via marshal",
        "high",
        "marshal is intended for Python byte code and is unsafe for untrusted inputs.",
        "Use json or msgpack."
    ),
]

# Regex Patterns for Path Traversal
PATH_TRAVERSAL_PATTERNS = [
    (
        r"""(?:open|os\.path\.join)\s*\([^)]*(?:request\.(?:args|GET|form|params)|req\.(?:query|params|body))""",
        "PATH-TRAVERSAL-INPUT",
        "Potential Path Traversal",
        "high",
        "File path directly constructed from unvalidated HTTP request parameters.",
        "Sanitize with os.path.basename() or resolve and verify against a root directory."
    ),
    (
        r"""(?:fs\.readFile|fs\.readFileSync|fs\.createReadStream)\s*\([^)]*req\.(?:query|params|body)""",
        "JS-PATH-TRAVERSAL",
        "Path Traversal in Node.js fs call",
        "high",
        "File system access directly uses unsanitized user input from request.",
        "Use path.basename() or path.resolve() and verify path starts with allowed root."
    ),
]

# Insecure Cryptography & Configuration
INSECURE_CRYPTO_PATTERNS = [
    (
        r"""hashlib\.(?:md5|sha1)\s*\(""",
        "WEAK-CRYPTO-HASH",
        "Weak Cryptographic Hash (MD5/SHA1)",
        "medium",
        "MD5 and SHA-1 are cryptographically broken and vulnerable to collision attacks.",
        "Use hashlib.sha256() or Argon2/bcrypt for passwords."
    ),
    (
        r"""verify\s*=\s*False""",
        "INSECURE-SSL-VERIFY-DISABLED",
        "Disabled SSL Certificate Verification",
        "high",
        "verify=False disables TLS certificate checks, making requests vulnerable to Man-in-the-Middle (MitM) attacks.",
        "Remove verify=False or provide a valid CA bundle path."
    ),
]


def scan_code_with_rules(code: str, language: str, filename: str = "snippet") -> List[RulesSecurityHit]:
    """
    Fast, deterministic pattern-matching security scanner.
    Returns list of discovered RulesSecurityHit items.
    """
    hits: List[RulesSecurityHit] = []
    lines = code.splitlines()
    is_py = language.lower() == "python"
    is_js = language.lower() in ("javascript", "typescript", "js", "ts")

    # 1. Regex line-by-line checks
    for line_idx, line in enumerate(lines, 1):
        # Skip comment-only lines
        stripped = line.strip()
        if not stripped:
            continue
        if is_py and stripped.startswith("#"):
            continue
        if is_js and (stripped.startswith("//") or stripped.startswith("/*")):
            continue

        # Check Hardcoded Secrets
        for pattern, rule_id, vuln_type, sev, msg, fix in SECRET_PATTERNS:
            if re.search(pattern, line):
                # Guard against common false positives (e.g. dummy placeholder)
                if any(fp in line.lower() for fp in ("your_api_key", "xxx", "placeholder", "dummy", "sample_token")):
                    continue
                hits.append(
                    RulesSecurityHit(
                        rule_id=rule_id,
                        vulnerability_type=vuln_type,
                        file=filename,
                        line=line_idx,
                        severity=sev,
                        message=msg,
                        matched_snippet=line.strip(),
                        suggested_fix=fix,
                    )
                )

        # Check SQL Injection
        for pattern, rule_id, vuln_type, sev, msg, fix in SQL_INJECTION_PATTERNS:
            if re.search(pattern, line):
                hits.append(
                    RulesSecurityHit(
                        rule_id=rule_id,
                        vulnerability_type=vuln_type,
                        file=filename,
                        line=line_idx,
                        severity=sev,
                        message=msg,
                        matched_snippet=line.strip(),
                        suggested_fix=fix,
                    )
                )

        # Check Command Injection
        for pattern, rule_id, vuln_type, sev, msg, fix in COMMAND_INJECTION_PATTERNS:
            if re.search(pattern, line):
                hits.append(
                    RulesSecurityHit(
                        rule_id=rule_id,
                        vulnerability_type=vuln_type,
                        file=filename,
                        line=line_idx,
                        severity=sev,
                        message=msg,
                        matched_snippet=line.strip(),
                        suggested_fix=fix,
                    )
                )

        # Check Deserialization
        if is_py:
            for pattern, rule_id, vuln_type, sev, msg, fix in DESERIALIZATION_PATTERNS:
                if re.search(pattern, line):
                    hits.append(
                        RulesSecurityHit(
                            rule_id=rule_id,
                            vulnerability_type=vuln_type,
                            file=filename,
                            line=line_idx,
                            severity=sev,
                            message=msg,
                            matched_snippet=line.strip(),
                            suggested_fix=fix,
                        )
                    )

        # Check Path Traversal
        for pattern, rule_id, vuln_type, sev, msg, fix in PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, line):
                hits.append(
                    RulesSecurityHit(
                        rule_id=rule_id,
                        vulnerability_type=vuln_type,
                        file=filename,
                        line=line_idx,
                        severity=sev,
                        message=msg,
                        matched_snippet=line.strip(),
                        suggested_fix=fix,
                    )
                )

        # Check Insecure Crypto
        if is_py:
            for pattern, rule_id, vuln_type, sev, msg, fix in INSECURE_CRYPTO_PATTERNS:
                if re.search(pattern, line):
                    hits.append(
                        RulesSecurityHit(
                            rule_id=rule_id,
                            vulnerability_type=vuln_type,
                            file=filename,
                            line=line_idx,
                            severity=sev,
                            message=msg,
                            matched_snippet=line.strip(),
                            suggested_fix=fix,
                        )
                    )

        # Check Eval / Exec in JS
        if is_js:
            if re.search(r"\beval\s*\(", line):
                hits.append(
                    RulesSecurityHit(
                        rule_id="JS-INSECURE-EVAL",
                        vulnerability_type="Insecure Dynamic Code Execution (eval)",
                        file=filename,
                        line=line_idx,
                        severity="critical",
                        message="eval() permits arbitrary code execution if passed untrusted data.",
                        matched_snippet=line.strip(),
                        suggested_fix="Avoid eval(); use JSON.parse() or specific dispatch maps.",
                    )
                )
            if re.search(r"\.innerHTML\s*=", line):
                hits.append(
                    RulesSecurityHit(
                        rule_id="JS-XSS-INNERHTML",
                        vulnerability_type="Cross-Site Scripting (XSS via innerHTML)",
                        file=filename,
                        line=line_idx,
                        severity="high",
                        message="Direct assignment to innerHTML bypasses HTML sanitization, allowing stored/reflected XSS.",
                        matched_snippet=line.strip(),
                        suggested_fix="Use textContent or a sanitized DOM library like DOMPurify.",
                    )
                )

    # 2. Python AST Analysis for deeper structural vulnerabilities
    if is_py:
        try:
            tree = ast.parse(code, filename=filename)
            for node in ast.walk(tree):
                # AST check for dangerous eval/exec
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                        hits.append(
                            RulesSecurityHit(
                                rule_id=f"PY-DANGEROUS-{node.func.id.upper()}",
                                vulnerability_type="Arbitrary Code Execution via eval/exec",
                                file=filename,
                                line=node.lineno,
                                column=node.col_offset,
                                severity="critical",
                                message=f"Use of {node.func.id}() enables arbitrary code execution.",
                                matched_snippet=f"{node.func.id}(...)",
                                suggested_fix="Replace dynamic code execution with safe data parsing like ast.literal_eval() or JSON.",
                            )
                        )
        except SyntaxError:
            pass

    # Deduplicate hits on same line and rule_id
    deduped: List[RulesSecurityHit] = []
    seen = set()
    for h in hits:
        key = (h.line, h.rule_id)
        if key not in seen:
            seen.add(key)
            deduped.append(h)

    return deduped
