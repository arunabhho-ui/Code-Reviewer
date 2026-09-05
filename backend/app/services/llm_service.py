import difflib
import json
import time
import uuid
from typing import List, Optional, Tuple, Dict, Any
import os
from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import (
    ReviewFinding,
    ReviewSummary,
    StaticFinding,
    TokenUsage,
    SeverityLevel,
    IssueCategory,
)

SYSTEM_PROMPT = """You are an elite Principal Software Engineer and Staff Security Reviewer.
Your task is to conduct an uncompromising, precise, and constructive code review on the provided source code.
You are given the user's code, target language, and any static analysis warnings detected by linters.

Review criteria:
1. Bugs & Correctness: Logical flaws, off-by-one errors, unhandled exceptions, race conditions, edge case failures, type errors, unclosed streams/handles.
2. Security: Injection vulnerabilities (SQL, command, XSS), unsafe deserialization, insecure cryptographic defaults, path traversal, authorization flaws.
3. Performance: Inefficient complexity (O(N^2) loops where O(N) is possible), memory leaks, excessive allocations, redundant IO/network queries.
4. Style & Best Practices: Idiomatic language conventions (PEP 8 for Python, ESLint/modern ES conventions for JS/TS), dead code, maintainability.

You must invoke the `submit_code_review` function with structured findings and the entire fixed file.
Provide accurate line numbers (1-indexed). For each finding, provide the exact original snippet and proposed fixed snippet.
"""

REVIEW_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_code_review",
        "description": "Submit structured code review findings and complete fixed code",
        "parameters": {
            "type": "object",
            "properties": {
                "findings": {
                    "type": "array",
                    "description": "List of discovered code findings",
                    "items": {
                        "type": "object",
                        "properties": {
                            "line": {"type": "integer", "description": "Line number where the issue occurs (1-indexed)"},
                            "severity": {"type": "string", "enum": ["critical", "high", "medium", "low", "info"]},
                            "category": {"type": "string", "enum": ["bug", "security", "performance", "style"]},
                            "title": {"type": "string", "description": "Concise summary of the finding"},
                            "explanation": {"type": "string", "description": "In-depth rationale, implications, and how to resolve it"},
                            "suggested_fix": {"type": "string", "description": "Proposed fix explanation or code"},
                            "original_code_snippet": {"type": "string", "description": "Original line(s) with issue"},
                            "fixed_code_snippet": {"type": "string", "description": "Target replacement line(s)"}
                        },
                        "required": ["line", "severity", "category", "title", "explanation"]
                    }
                },
                "raw_fixed_code": {
                    "type": "string",
                    "description": "The complete, runnable source code file with all fixes applied"
                },
                "overall_summary": {
                    "type": "string",
                    "description": "Executive summary of findings"
                }
            },
            "required": ["findings", "raw_fixed_code"]
        }
    }
}


def calculate_diff(original: str, modified: str, filename: str = "snippet") -> str:
    """Generates a standard unified diff string between original and modified code."""
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


def calculate_finding_diff(orig_snippet: Optional[str], fixed_snippet: Optional[str]) -> Optional[str]:
    """Generates inline snippet diff."""
    if not orig_snippet or not fixed_snippet:
        return None
    orig_lines = orig_snippet.splitlines(keepends=True)
    fixed_lines = fixed_snippet.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        fixed_lines,
        fromfile="original",
        tofile="suggested_fix",
        n=2
    )
    return "".join(diff)


def compute_summary_and_score(findings: List[ReviewFinding], static_findings: List[StaticFinding]) -> ReviewSummary:
    """Computes category tallies, severity tallies, and an overall code quality score (0-100)."""
    summary = ReviewSummary()
    summary.total_issues = len(findings)
    summary.static_analysis_passed = len(static_findings) == 0

    penalty = 0
    for f in findings:
        if f.category == "bug":
            summary.bugs += 1
        elif f.category == "security":
            summary.security += 1
        elif f.category == "performance":
            summary.performance += 1
        elif f.category == "style":
            summary.style += 1

        if f.severity == "critical":
            summary.critical += 1
            penalty += 30
        elif f.severity == "high":
            summary.high += 1
            penalty += 15
        elif f.severity == "medium":
            summary.medium += 1
            penalty += 8
        elif f.severity == "low":
            summary.low += 1
            penalty += 3
        elif f.severity == "info":
            summary.info += 1
            penalty += 1

    summary.overall_score = max(0, 100 - penalty)
    return summary


def synthesize_fallback_findings(code: str, static_findings: List[StaticFinding], filename: str) -> Tuple[List[ReviewFinding], str, Optional[str]]:
    """Synthesizes review findings from static analysis when LLM API is unavailable."""
    findings: List[ReviewFinding] = []
    lines = code.splitlines()

    for sf in static_findings:
        line_no = min(max(1, sf.line), max(1, len(lines)))
        orig_line = lines[line_no - 1] if 0 <= line_no - 1 < len(lines) else ""
        findings.append(
            ReviewFinding(
                id=str(uuid.uuid4())[:8],
                file=filename,
                line=line_no,
                severity=sf.severity,
                category=sf.category,
                title=f"Static Check: {sf.rule}",
                explanation=sf.message,
                suggested_fix=f"Review line {line_no} to resolve {sf.rule}",
                original_code_snippet=orig_line,
                fixed_code_snippet=orig_line,
                diff=None
            )
        )

    warning_msg = (
        "Note: Reviewed using deterministic static analysis fallback mode. "
        "Configure GROQ_API_KEY to activate Groq deep AI code review."
    )
    return findings, code, warning_msg


async def review_code_with_llm(
    code: str,
    language: str,
    filename: str,
    static_findings: List[StaticFinding],
    api_key_override: Optional[str] = None,
    model_override: Optional[str] = None,
    cross_file_context: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[ReviewFinding], ReviewSummary, Optional[str], Optional[TokenUsage], Optional[str]]:
    """
    Calls Groq Cloud via the OpenAI-compatible API.
    Returns (findings, summary, raw_fixed_code, token_usage, warning_message).
    """
    api_key = api_key_override or settings.GROQ_API_KEY or os.getenv('GROQ_API_KEY')
    model = model_override or settings.active_model
    if model not in settings.VALID_GROQ_MODELS:
        model = settings.active_model
    # Use temperature and reasoning_effort similar to property-post-maker for better quality
    temperature = 0.8
    if not api_key or api_key.strip() == "":
        findings, fixed_code, warning = synthesize_fallback_findings(code, static_findings, filename)
        summary = compute_summary_and_score(findings, static_findings)
        return findings, summary, fixed_code, None, warning

    client = AsyncOpenAI(api_key=api_key, base_url=settings.active_base_url)

    static_context = ""
    if static_findings:
        static_context = "Static Analysis Pre-Pass Findings:\n" + "\n".join(
            [f"- Line {sf.line} [{sf.severity.upper()}] ({sf.category}): {sf.rule} - {sf.message}" for sf in static_findings]
        )
    else:
        static_context = "Static Analysis Pre-Pass: 0 issues found."

    rag_context_section = ""
    if cross_file_context:
        rag_context_section = "\nCross-File Context (Retrieved from Repository Chroma Index):\n"
        for ctx in cross_file_context:
            rag_context_section += f"--- [{ctx.get('symbol_type', 'symbol').upper()}] `{ctx.get('symbol_name')}` in `{ctx.get('file_path')}` ({ctx.get('relevance_reason', '')}) ---\n"
            rag_context_section += f"```{ctx.get('language', language)}\n{ctx.get('code_chunk', '')}\n```\n"

    user_message = f"""Please review the following {language} file: `{filename}`

{static_context}
{rag_context_section}
Source Code under Review:
```{language}
{code}
```

Identify all bugs, security flaws, performance issues, and style defects. Propose precise fixes and generate the full corrected code file."""

    try:
        response = await client.chat.completions.create(
            model=model,
            max_tokens=4096,
            temperature=0.8,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            tools=[REVIEW_TOOL],
            tool_choice={"type": "function", "function": {"name": "submit_code_review"}},
        )

        findings: List[ReviewFinding] = []
        raw_fixed_code = code

        choice = response.choices[0]
        tool_calls = choice.message.tool_calls or []
        for tc in tool_calls:
            if tc.function.name == "submit_code_review":
                input_data = json.loads(tc.function.arguments)
                raw_findings = input_data.get("findings", [])
                raw_fixed_code = input_data.get("raw_fixed_code", code)

                for item in raw_findings:
                    orig_snippet = item.get("original_code_snippet")
                    fixed_snippet = item.get("fixed_code_snippet")
                    finding_diff = calculate_finding_diff(orig_snippet, fixed_snippet)

                    findings.append(
                        ReviewFinding(
                            id=str(uuid.uuid4())[:8],
                            file=filename,
                            line=int(item.get("line", 1)),
                            severity=item.get("severity", "medium"),
                            category=item.get("category", "bug"),
                            title=item.get("title", "Code Issue"),
                            explanation=item.get("explanation", ""),
                            suggested_fix=item.get("suggested_fix", ""),
                            original_code_snippet=orig_snippet,
                            fixed_code_snippet=fixed_snippet,
                            diff=finding_diff
                        )
                    )
                break

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        # Approximate cost (update when xAI publishes exact pricing)
        estimated_cost = (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)
        token_usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=round(estimated_cost, 5)
        )

        summary = compute_summary_and_score(findings, static_findings)
        return findings, summary, raw_fixed_code, token_usage, None

    except Exception as e:
        findings, fixed_code, _ = synthesize_fallback_findings(code, static_findings, filename)
        summary = compute_summary_and_score(findings, static_findings)
        warning_msg = f"Groq API Notice: {str(e)}. Fallback static analysis results displayed."
        return findings, summary, fixed_code, None, warning_msg
