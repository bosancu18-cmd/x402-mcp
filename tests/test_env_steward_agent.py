"""Env steward is an operator cloud agent — never a public discovery listing."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.tools_registry import EXPECTED_TOOL_NAMES

client = TestClient(app)

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / ".claude" / "agents" / "x402-env-steward.md"
GROK = ROOT / ".grok" / "agents" / "x402-env-steward.md"

REQUIRED_PROMPT_MARKERS = (
    "x402-mcp.env",
    "EVM_PRIVATE_KEY",
    "Google Drive",
    "Never commit",
    "OPERATOR_TOKEN",
    "agents.json",
)


def _prompt(path: Path) -> str:
    assert path.is_file(), path
    text = path.read_text(encoding="utf-8")
    assert text.lstrip().startswith("---")
    assert "name: x402-env-steward" in text
    return text


def test_env_steward_prompts_exist_and_forbid_secret_leakage() -> None:
    for path in (CLAUDE, GROK):
        text = _prompt(path)
        lower = text.lower()
        for marker in REQUIRED_PROMPT_MARKERS:
            assert marker.lower() in lower, f"{path} missing {marker!r}"
        assert "share_file" in text
        assert "wallet_configured" in text or "seller-only" in lower


def test_env_steward_is_not_a_public_mcp_tool() -> None:
    assert "x402-env-steward" not in EXPECTED_TOOL_NAMES
    assert "env-steward" not in EXPECTED_TOOL_NAMES


def test_env_steward_absent_from_public_agents_json() -> None:
    body = client.get("/.well-known/agents.json").json()
    ids = {agent.get("id") for agent in body.get("agents", [])}
    assert "x402-env-steward" not in ids
    blob = str(body).lower()
    assert "x402-mcp.env" not in blob
    assert "google drive" not in blob


def test_env_steward_absent_from_public_openapi() -> None:
    spec = client.get("/openapi.json").json()
    blob = str(spec).lower()
    assert "x402-env-steward" not in blob
    assert "x402-mcp.env" not in blob
