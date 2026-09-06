from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


SeverityLevel = Literal["critical", "high", "medium", "low", "info"]
IssueCategory = Literal["bug", "security", "performance", "style"]
SupportedLanguage = Literal["python", "javascript", "typescript", "c", "java"]


class ReviewRequest(BaseModel):
    code: str = Field(..., min_length=1, description="Code snippet to review")
    language: SupportedLanguage = Field("python", description="Language of the code")
    filename: Optional[str] = Field("snippet.py", description="Filename or path")
    api_key: Optional[str] = Field(None, description="Optional Groq API key override from client")
    model: Optional[str] = Field(None, description="Optional Groq model override")
    run_static_analysis: bool = Field(True, description="Whether to run static linter first")
    run_security_pass: bool = Field(False, description="Whether to run dedicated security review pass")


class StaticFinding(BaseModel):
    file: str
    line: int
    column: Optional[int] = 0
    rule: str
    message: str
    severity: SeverityLevel
    category: IssueCategory


class ReviewFinding(BaseModel):
    id: Optional[str] = None
    file: str
    line: int
    severity: SeverityLevel
    category: IssueCategory
    title: str
    explanation: str
    suggested_fix: Optional[str] = None
    original_code_snippet: Optional[str] = None
    fixed_code_snippet: Optional[str] = None
    diff: Optional[str] = None


class SecurityFinding(BaseModel):
    id: Optional[str] = None
    file: str
    line: int
    severity: SeverityLevel  # critical, high, medium, low
    vulnerability_type: str
    title: str
    explanation: str
    exploitability: str
    suggested_fix: Optional[str] = None
    original_code_snippet: Optional[str] = None
    fixed_code_snippet: Optional[str] = None
    diff: Optional[str] = None
    confidence: Literal["high", "llm_inferred", "rules_only"] = "llm_inferred"
    rules_confirmed: bool = False
    rule_id: Optional[str] = None


class SecurityReviewSummary(BaseModel):
    total_vulnerabilities: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    rules_confirmed_count: int = 0


class ReviewSummary(BaseModel):
    total_issues: int = 0
    bugs: int = 0
    security: int = 0
    performance: int = 0
    style: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0
    static_analysis_passed: bool = True
    overall_score: int = 100


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class ReviewResponse(BaseModel):
    id: str
    filename: str
    language: SupportedLanguage
    static_findings: List[StaticFinding] = []
    findings: List[ReviewFinding] = []
    security_findings: Optional[List[SecurityFinding]] = None
    security_summary: Optional[SecurityReviewSummary] = None
    summary: ReviewSummary
    execution_time_ms: float
    token_usage: Optional[TokenUsage] = None
    raw_fixed_code: Optional[str] = None
    warning: Optional[str] = None


class AgentFixRequest(BaseModel):
    code: str = Field(..., min_length=1, description="Source code containing the bug")
    language: SupportedLanguage = Field("python", description="Programming language")
    filename: Optional[str] = Field(None, description="Target filename; inferred from language when omitted")
    bug_description: Optional[str] = Field(None, description="Description of the bug to fix")
    test_code: Optional[str] = Field(None, description="Optional existing test suite to run against")
    api_key: Optional[str] = Field(None, description="Optional Groq API key")
    model: Optional[str] = Field(None, description="Optional model override")
    max_retries: int = Field(3, ge=1, le=5, description="Maximum number of repair attempts")


class AgentStepData(BaseModel):
    step_type: str
    message: str
    timestamp: float
    data: Optional[Dict[str, Any]] = None


class AgentFixResponse(BaseModel):
    success: bool
    verified_in_sandbox: bool
    total_attempts: int
    final_code: str
    final_diff: Optional[str] = None
    test_code: Optional[str] = None
    test_type: Optional[str] = None  # "pre_existing" or "smoke_test"
    token_usage: Optional[TokenUsage] = None
    steps: List[Dict[str, Any]] = []
    message: str


class OpenPRRequest(BaseModel):
    owner: str = Field(..., description="Repository owner (user or org)")
    repo: str = Field(..., description="Repository name")
    base_branch: Optional[str] = Field(None, description="Target base branch for PR (e.g. main)")
    file_path: str = Field(..., description="Relative path of file to update")
    fixed_code: str = Field(..., description="The sandbox-verified patched source code")
    fix_summary: Optional[str] = Field("Verified automated fix from AI Code Reviewer", description="Summary of fix")
    finding_details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Details of addressed finding")
    test_verification_type: str = Field("smoke_test", description="'pre_existing' or 'smoke_test'")
    github_token: str = Field(..., min_length=1, description="GitHub Personal Access Token")


class OpenPRResponse(BaseModel):
    success: bool
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    branch: Optional[str] = None
    message: str

