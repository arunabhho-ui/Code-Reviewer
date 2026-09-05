import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock
from app.main import app
from app.services.security_scanner import scan_code_with_rules, RulesSecurityHit
from app.services.security_service import cross_reference_findings, compute_security_summary
from app.models.schemas import SecurityFinding


def test_scan_sql_injection_python():
    vuln_code = '''
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
'''
    hits = scan_code_with_rules(vuln_code, "python", "db.py")
    assert len(hits) >= 1
    assert any("SQL Injection" in h.vulnerability_type for h in hits)
    assert any(h.severity == "critical" for h in hits)


def test_scan_hardcoded_secrets():
    vuln_code = '''
AWS_KEY = "AKIA1234567890ABCDEF"
GITHUB_SECRET = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
api_key = "abcdef1234567890abcdef"
'''
    hits = scan_code_with_rules(vuln_code, "python", "config.py")
    assert len(hits) >= 2
    vuln_types = [h.vulnerability_type for h in hits]
    assert any("Hardcoded" in vt for vt in vuln_types)


def test_scan_command_injection():
    vuln_code = '''
import os
import subprocess

def run_cmd(user_input):
    os.system("echo " + user_input)
    subprocess.run("ls " + user_input, shell=True)
'''
    hits = scan_code_with_rules(vuln_code, "python", "shell_tool.py")
    assert len(hits) >= 2
    rule_ids = [h.rule_id for h in hits]
    assert "CMD-INJECTION-OS-SYSTEM" in rule_ids
    assert "CMD-INJECTION-SHELL-TRUE" in rule_ids


def test_scan_unsafe_deserialization():
    vuln_code = '''
import pickle
import yaml

def load_payload(raw):
    data = pickle.loads(raw)
    cfg = yaml.load(raw, Loader=yaml.Loader)
'''
    hits = scan_code_with_rules(vuln_code, "python", "loader.py")
    assert len(hits) >= 2
    rule_ids = [h.rule_id for h in hits]
    assert "UNSAFE-DESERIALIZATION-PICKLE" in rule_ids
    assert "UNSAFE-YAML-LOAD" in rule_ids


def test_scan_js_security_patterns():
    js_vuln = '''
function executeUserQuery(db, userInput) {
    db.query(`SELECT * FROM accounts WHERE name = '${userInput}'`);
    eval(userInput);
}
'''
    hits = scan_code_with_rules(js_vuln, "javascript", "handler.js")
    assert len(hits) >= 2
    rule_ids = [h.rule_id for h in hits]
    assert "JS-SQLI-TEMPLATE-LITERAL" in rule_ids
    assert "JS-INSECURE-EVAL" in rule_ids


def test_cross_referencing_and_ranking():
    rules_hits = [
        RulesSecurityHit(
            rule_id="SQLI-FSTRING",
            vulnerability_type="SQL Injection",
            file="app.py",
            line=10,
            severity="critical",
            message="SQL injection detected",
            matched_snippet="cursor.execute(f'SELECT...')"
        )
    ]
    llm_findings = [
        SecurityFinding(
            id="find-1",
            file="app.py",
            line=10,
            severity="critical",
            vulnerability_type="SQL Injection",
            title="Raw SQL concatenation",
            explanation="Attacker can bypass auth",
            exploitability="Arbitrary database dump via ' OR '1'='1",
            suggested_fix="Use parameterized queries",
        ),
        SecurityFinding(
            id="find-2",
            file="app.py",
            line=25,
            severity="medium",
            vulnerability_type="Weak Cryptography",
            title="Insecure MD5",
            explanation="MD5 hash used",
            exploitability="Preimage collisions possible",
            suggested_fix="Use SHA-256",
        )
    ]

    code = "\n" * 30
    ranked = cross_reference_findings(llm_findings, rules_hits, "app.py", code)

    # find-1 should be high confidence / rules_confirmed because rules hit is at line 10
    assert ranked[0].rules_confirmed is True
    assert ranked[0].confidence == "high"
    assert ranked[0].rule_id == "SQLI-FSTRING"

    # find-2 has no matching rule hit -> llm_inferred
    assert ranked[1].confidence == "llm_inferred"
    assert ranked[1].rules_confirmed is False

    summary = compute_security_summary(ranked)
    assert summary.total_vulnerabilities == 2
    assert summary.critical == 1
    assert summary.medium == 1
    assert summary.rules_confirmed_count == 1


@pytest.mark.asyncio
async def test_single_file_review_unaffected():
    """Verify Single-File Review endpoint behavior is completely unchanged (no security pass by default)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "code": "def hello():\n    return 'world'\n",
            "language": "python",
            "filename": "hello.py",
            "run_static_analysis": True,
            "run_security_pass": False
        }
        response = await client.post("/api/review", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "findings" in data
        assert "summary" in data
        # In Single-File Review mode, security_findings is None
        assert data.get("security_findings") is None


@pytest.mark.asyncio
async def test_dedicated_security_pass_enabled():
    """Verify that when run_security_pass is True (PR / RAG mode), security_findings are returned."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "code": "import os\ndef run(p):\n    os.system(p)\n",
            "language": "python",
            "filename": "shell.py",
            "run_static_analysis": True,
            "run_security_pass": True
        }
        response = await client.post("/api/review", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("security_findings") is not None
        assert len(data["security_findings"]) > 0
        assert data.get("security_summary") is not None


@pytest.mark.asyncio
async def test_open_pr_validation():
    """Verify open-pr endpoint rejects requests with empty or missing token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "owner": "octocat",
            "repo": "hello-world",
            "file_path": "main.py",
            "fixed_code": "print('fixed')",
            "github_token": ""  # empty
        }
        response = await client.post("/api/github/open-pr", json=payload)
        assert response.status_code in (400, 422)
