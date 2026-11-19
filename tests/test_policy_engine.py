import pytest
from mcp.models import PolicyAction, RiskLevel, ServerTrustLevel
from mcp.policy.policy_engine import (
    CommandSecurityViolation,
    PathSecurityViolation,
    ToolPolicyEngine,
)


@pytest.fixture
def engine():
    return ToolPolicyEngine()


def test_safe_tool_is_allowed(engine: ToolPolicyEngine):
    decision = engine.authorize("read_file", RiskLevel.SAFE)
    assert decision.decision == PolicyAction.ALLOW
    assert not decision.requires_approval


def test_controlled_tool_command_policy(engine: ToolPolicyEngine):
    # Allowed command
    decision = engine.authorize(
        "run_tests",
        RiskLevel.CONTROLLED,
        arguments={"command": "pytest -v"},
    )
    assert decision.decision == PolicyAction.ALLOW

    # Disallowed command
    decision_bad = engine.authorize(
        "run_tests",
        RiskLevel.CONTROLLED,
        arguments={"command": "curl http://malicious.site"},
    )
    assert decision_bad.decision == PolicyAction.DENY
    assert "Disallowed" in decision_bad.reason or "not in the allowed" in decision_bad.reason


def test_disallowed_shell_injection_patterns(engine: ToolPolicyEngine):
    dangerous_commands = [
        "pytest; rm -rf /",
        "pytest && cat /etc/passwd",
        "pytest | bash",
        "pytest > output.txt",
        "pytest `whoami`",
        "pytest $SECRET",
    ]
    for cmd in dangerous_commands:
        decision = engine.authorize(
            "run_tests",
            RiskLevel.CONTROLLED,
            arguments={"command": cmd},
        )
        assert decision.decision == PolicyAction.DENY
        assert "Disallowed command pattern detected" in decision.reason


def test_path_traversal_prevention(engine: ToolPolicyEngine):
    workspace = "."
    # Normal relative path within workspace
    valid_path = engine.validate_workspace_path(workspace, "apps/api/main.py")
    assert valid_path.exists()

    # Directory traversal escapes
    with pytest.raises(PathSecurityViolation):
        engine.validate_workspace_path(workspace, "../../../etc/passwd")

    with pytest.raises(PathSecurityViolation):
        engine.validate_workspace_path(workspace, "../../secret.txt")


def test_dangerous_tool_requires_approval_and_succeeds_when_approved(engine: ToolPolicyEngine):
    # 1. Unapproved call -> REQUIRE_APPROVAL
    decision = engine.authorize("push_branch", RiskLevel.DANGEROUS)
    assert decision.decision == PolicyAction.REQUIRE_APPROVAL
    assert decision.requires_approval
    assert decision.approval_token is not None

    token = decision.approval_token

    # 2. Register human approval
    engine.register_approval(token, "push_branch", user_id="usr_admin")
    assert engine.is_approved(token, "push_branch")

    # 3. Call again with approval token -> ALLOW
    approved_decision = engine.authorize(
        "push_branch",
        RiskLevel.DANGEROUS,
        approval_token=token,
    )
    assert approved_decision.decision == PolicyAction.ALLOW
    assert not approved_decision.requires_approval

    # 4. Token is consumed (replay attack prevention)
    assert not engine.is_approved(token, "push_branch")


def test_untrusted_server_policy(engine: ToolPolicyEngine):
    # Untrusted server can run SAFE
    safe_dec = engine.authorize(
        "read_file",
        RiskLevel.SAFE,
        server_trust=ServerTrustLevel.UNTRUSTED,
    )
    assert safe_dec.decision == PolicyAction.ALLOW

    # Untrusted server CANNOT run CONTROLLED
    ctrl_dec = engine.authorize(
        "run_tests",
        RiskLevel.CONTROLLED,
        server_trust=ServerTrustLevel.UNTRUSTED,
    )
    assert ctrl_dec.decision == PolicyAction.DENY


def test_disabled_server_and_tool_policy(engine: ToolPolicyEngine):
    disabled_srv = engine.authorize(
        "read_file",
        RiskLevel.SAFE,
        server_trust=ServerTrustLevel.DISABLED,
    )
    assert disabled_srv.decision == PolicyAction.DENY

    disabled_tool = engine.authorize(
        "read_file",
        RiskLevel.SAFE,
        tool_enabled=False,
    )
    assert disabled_tool.decision == PolicyAction.DENY
