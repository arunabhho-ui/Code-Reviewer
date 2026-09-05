import difflib
import json
import os
import time
import uuid
from typing import List, Optional, Tuple, Dict, Any
from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import (
    SecurityFinding,
    SecurityReviewSummary,
    SeverityLevel,
)
from app.services.security_scanner import scan_code_with_rules, RulesSecurityHit

SECURITY_SYSTEM_PROMPT = """You are a Principal Application Security Engineer (AppSec) and offensive penetration tester.
Your task is to conduct an uncompromising, deep security vulnerability review on the provided source code.
Focus exclusively on security vulnerabilities, real-world exploitability, and attack vectors.
Do NOT report general code style, formatting, or benign edge cases unless they present an exploitable security flaw.

You must explicitly check for, at minimum:
1. SQL Injection: string concatenation, f-strings, or % formatting in queries instead of parameterized statements.
2. Hardcoded Secrets/Credentials: API keys, tokens, passwords, private keys, authorization tokens.
3. Unsafe Deserialization: pickle, unsafe yaml loading, marshal on untrusted input.
4. Command Injection: os.system, subprocess with shell=True, child_process.exec with concatenated user inputs.
5. Path Traversal: direct file operations using unvalidated paths or request parameters.
6. Missing Input Validation & Sanitization: XSS, unvalidated redirects, unconstrained inputs.
7. Insecure Dynamic Code Execution: eval, exec, new Function with untrusted data.
8. Weak or Missing Auth Checks: sensitive operations, admin actions, or data modifications without authentication or authorization.
9. Known-Vulnerable Patterns: weak hashing (MD5/SHA1), disabled SSL verification (verify=False), insecure temporary file usage.

You must invoke the `submit_security_review` function with structured security findings and secure fixes.
Severity must reflect real-world exploitability:
- 'critical': Remote code execution, direct SQL injection, exposed master credentials, trivial authentication bypass.
- 'high': Stored XSS, privilege escalation, path traversal with data leak, unsafe deserialization of internal payloads.
- 'medium': Missing rate limits on sensitive endpoints, weak crypto, CSRF, insecure cookie flags.
- 'low': Information disclosure, verbose error messages, defense-in-depth improvements.
Provide an in-depth explanation of how an attacker could exploit the issue in practice, and a precise secure fix.
"""

SECURITY_REVIEW_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_security_review",
        "description": "Submit structured security vulnerability findings with exploitability details",
        "parameters": {
            "type": "object",
            "properties": {
                "security_findings": {
                    "type": "array",
                    "description": "List of discovered security vulnerabilities",
                    "items": {
                        "type": "object",
                        "properties": {
                            "line": {
                                "type": "integer",
                                "description": "Line number where the vulnerability is located (1-indexed)"
                            },
                            "severity": {
                                "type": "string",
                                "enum": ["critical", "high", "medium", "low"],
                                "description": "Severity based on real-world exploitability"
                            },
                            "vulnerability_type": {
                                "type": "string",
                                "description": "Standard vulnerability classification (e.g., SQL Injection, Hardcoded Secret, Command Injection, Path Traversal)"
                            },
                            "title": {
                                "type": "string",
                                "description": "Concise summary of the vulnerability"
                            },
                            "explanation": {
                                "type": "string",
                                "description": "Technical description of the vulnerability"
                            },
                            "exploitability": {
                                "type": "string",
                                "description": "Detailed explanation of how an attacker can exploit this in practice and the realistic blast radius"
                            },
                            "suggested_fix": {
                                "type": "string",
                                "description": "Prescriptive remediation guidance or replacement code"
                            },
                            "original_code_snippet": {
                                "type": "string",
                                "description": "The vulnerable line(s) of code"
                            },
                            "fixed_code_snippet": {
                                "type": "string",
                                "description": "The secure replacement line(s) of code"
                            }
                        },
                        "required": ["line", "severity", "vulnerability_type", "title", "explanation", "exploitability", "suggested_fix"]
                    }
                },
                "security_summary": {
                    "type": "string",
                    "description": "Executive summary of the security posture"
                }
            },
            "required": ["security_findings"]
        }
    }
}

SEVERITY_WEIGHT = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "info": 0,
}


def calculate_finding_diff(orig_snippet: Optional[str], fixed_snippet: Optional[str]) -> Optional[str]:
    """Generates inline snippet diff between original and fixed code."""
    if not orig_snippet or not fixed_snippet:
        return None
    orig_lines = orig_snippet.splitlines(keepends=True)
    fixed_lines = fixed_snippet.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        fixed_lines,
        fromfile="vulnerable",
        tofile="secure_fix",
        n=2
    )
    return "".join(diff)


def compute_security_summary(findings: List[SecurityFinding]) -> SecurityReviewSummary:
    """Aggregates security vulnerability counts and verified rule counts."""
    summary = SecurityReviewSummary()
    summary.total_vulnerabilities = len(findings)
    for f in findings:
        if f.severity == "critical":
            summary.critical += 1
        elif f.severity == "high":
            summary.high += 1
        elif f.severity == "medium":
            summary.medium += 1
        elif f.severity == "low":
            summary.low += 1

        if f.rules_confirmed:
            summary.rules_confirmed_count += 1

    return summary


def cross_reference_findings(
    llm_findings: List[SecurityFinding],
    rules_hits: List[RulesSecurityHit],
    filename: str,
    code: str
) -> List[SecurityFinding]:
    """
    Cross-references LLM findings with deterministic rules-based hits.
    - Findings that both rules scan and LLM agree on get confidence: "high", rules_confirmed: True.
    - Remaining rules hits not covered by LLM are added with confidence: "rules_only".
    - Returns findings ranked by severity: critical > high > medium > low.
    """
    matched_rule_indices = set()
    enriched_findings: List[SecurityFinding] = []
    lines = code.splitlines()

    for finding in llm_findings:
        is_confirmed = False
        matched_hit: Optional[RulesSecurityHit] = None

        for idx, hit in enumerate(rules_hits):
            # Match if on nearby line (within 2 lines) or exact vulnerability type similarity
            line_distance = abs(finding.line - hit.line)
            vuln_similarity = (
                hit.vulnerability_type.lower() in finding.vulnerability_type.lower()
                or finding.vulnerability_type.lower() in hit.vulnerability_type.lower()
            )

            if line_distance <= 2 or vuln_similarity:
                is_confirmed = True
                matched_hit = hit
                matched_rule_indices.add(idx)
                break

        if is_confirmed and matched_hit:
            finding.confidence = "high"
            finding.rules_confirmed = True
            finding.rule_id = matched_hit.rule_id
        else:
            finding.confidence = "llm_inferred"
            finding.rules_confirmed = False

        if not finding.diff and finding.original_code_snippet and finding.fixed_code_snippet:
            finding.diff = calculate_finding_diff(finding.original_code_snippet, finding.fixed_code_snippet)

        enriched_findings.append(finding)

    # Add any rules hits that the LLM missed entirely as rules_only findings
    for idx, hit in enumerate(rules_hits):
        if idx not in matched_rule_indices:
            line_no = min(max(1, hit.line), max(1, len(lines)))
            orig_line = lines[line_no - 1] if 0 <= line_no - 1 < len(lines) else hit.matched_snippet
            enriched_findings.append(
                SecurityFinding(
                    id=str(uuid.uuid4())[:8],
                    file=filename,
                    line=line_no,
                    severity=hit.severity,
                    vulnerability_type=hit.vulnerability_type,
                    title=f"Static Rule: {hit.rule_id}",
                    explanation=hit.message,
                    exploitability=f"Identified by deterministic security pattern '{hit.rule_id}'. May be weaponized depending on input source.",
                    suggested_fix=hit.suggested_fix,
                    original_code_snippet=orig_line,
                    fixed_code_snippet=None,
                    diff=None,
                    confidence="rules_only",
                    rules_confirmed=True,
                    rule_id=hit.rule_id
                )
            )

    # Sort severity descending (critical -> high -> medium -> low), then rules_confirmed first
    enriched_findings.sort(
        key=lambda f: (SEVERITY_WEIGHT.get(f.severity, 0), 1 if f.rules_confirmed else 0),
        reverse=True
    )

    return enriched_findings


async def run_dedicated_security_review(
    code: str,
    language: str,
    filename: str,
    api_key_override: Optional[str] = None,
    model_override: Optional[str] = None,
    cross_file_context: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[SecurityFinding], SecurityReviewSummary]:
    """
    Dedicated Security Review Pass (scoped to GitHub PR Mode & Whole-Repo RAG Mode).
    1. Runs fast deterministic rules pre-pass first.
    2. Runs dedicated AppSec LLM pass using a focused security prompt.
    3. Cross-references LLM findings with rules hits for high confidence scoring.
    """
    # 1. Deterministic rules-based pre-pass
    rules_hits = scan_code_with_rules(code=code, language=language, filename=filename)

    api_key = api_key_override or settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
    model = model_override or settings.active_model
    if model not in settings.VALID_GROQ_MODELS:
        model = settings.active_model

    # If no API key is present, fallback directly to rules hits
    if not api_key or not api_key.strip():
        fallback_findings = cross_reference_findings([], rules_hits, filename, code)
        return fallback_findings, compute_security_summary(fallback_findings)

    # 2. LLM dedicated AppSec review pass
    client = AsyncOpenAI(api_key=api_key, base_url=settings.active_base_url)

    rules_context_str = ""
    if rules_hits:
        rules_context_str = "Deterministic Security Pre-Scan Hits:\n" + "\n".join(
            [f"- Line {h.line} [{h.severity.upper()}] ({h.rule_id}): {h.message}" for h in rules_hits]
        )
    else:
        rules_context_str = "Deterministic Security Pre-Scan: No static rule triggers."

    rag_section = ""
    if cross_file_context:
        rag_section = "\nCross-File Context (Repository Chroma Index):\n"
        for ctx in cross_file_context:
            rag_section += f"--- [{ctx.get('symbol_type', 'symbol').upper()}] `{ctx.get('symbol_name')}` in `{ctx.get('file_path')}` ---\n"
            rag_section += f"```{ctx.get('language', language)}\n{ctx.get('code_chunk', '')}\n```\n"

    user_prompt = f"""Perform a dedicated, security-focused review on `{filename}` ({language}).

{rules_context_str}
{rag_section}
Target Code for Security Audit:
```{language}
{code}
```

Carefully inspect for SQL injection, hardcoded credentials, unsafe deserialization, command injection, path traversal, missing validation, eval/exec, and weak authorization.
Call the `submit_security_review` tool with your findings."""

    try:
        response = await client.chat.completions.create(
            model=model,
            max_tokens=4096,
            temperature=0.4,  # Lower temperature for security accuracy
            messages=[
                {"role": "system", "content": SECURITY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            tools=[SECURITY_REVIEW_TOOL],
            tool_choice={"type": "function", "function": {"name": "submit_security_review"}},
        )

        llm_findings: List[SecurityFinding] = []
        choice = response.choices[0]
        tool_calls = choice.message.tool_calls or []

        for tc in tool_calls:
            if tc.function.name == "submit_security_review":
                args = json.loads(tc.function.arguments)
                raw_items = args.get("security_findings", [])

                for item in raw_items:
                    orig_snippet = item.get("original_code_snippet")
                    fixed_snippet = item.get("fixed_code_snippet")
                    diff = calculate_finding_diff(orig_snippet, fixed_snippet)

                    llm_findings.append(
                        SecurityFinding(
                            id=str(uuid.uuid4())[:8],
                            file=filename,
                            line=int(item.get("line", 1)),
                            severity=item.get("severity", "medium"),
                            vulnerability_type=item.get("vulnerability_type", "Security Vulnerability"),
                            title=item.get("title", "Security Flaw"),
                            explanation=item.get("explanation", ""),
                            exploitability=item.get("exploitability", "Vulnerability is potentially exploitable."),
                            suggested_fix=item.get("suggested_fix"),
                            original_code_snippet=orig_snippet,
                            fixed_code_snippet=fixed_snippet,
                            diff=diff,
                        )
                    )
                break

        # 3. Cross-reference with deterministic rules scan hits
        final_findings = cross_reference_findings(llm_findings, rules_hits, filename, code)
        summary = compute_security_summary(final_findings)
        return final_findings, summary

    except Exception:
        # Fallback to rules hits on any LLM call failure
        fallback_findings = cross_reference_findings([], rules_hits, filename, code)
        return fallback_findings, compute_security_summary(fallback_findings)
