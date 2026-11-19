# Devaura Security & Policy Model

## 1. Security Principles

Devaura operates within developer repositories, executes tests, and prepares code patches. Because automated code execution and repository modification present inherent risk, Devaura adopts an uncompromising defense-in-depth posture:

1. **Least Privilege**: The AI agent never receives raw shell access on the host machine.
2. **Deterministic Sandboxing**: All user code, dependency installations, and test runs execute in strictly bounded ephemeral sandbox environments.
3. **Multi-Tier Tool Risk Classification**: Every tool exposed by any MCP server is categorized and governed by policy.
4. **Human-in-the-Loop Approval Gates**: Dangerous mutations (pushing code to remote repositories, opening PRs, merging) and repair plans require human approval.
5. **Secret Sanitization**: Automated redaction of tokens, private keys, passwords, and `.env` payloads before sending context to models or logging.
6. **Path Traversal Guards**: Every file access tool verifies that target paths resolve strictly within the designated workspace boundary.

---

## 2. Tool Risk Classification Matrix

Devaura categorizes all MCP and agent tools into three risk tiers:

```
[ SAFE ]
├── read_file (bounded line ranges, path-checked)
├── search_code (ripgrep / AST queries)
├── git_history / git_log / git_blame
├── inspect_diff
├── analyze_repository
└── find_related_tests

[ CONTROLLED ]
├── apply_patch (workspace-isolated)
├── run_tests (sandbox-isolated, CPU/Memory bounded)
├── run_linter (sandbox-isolated)
├── run_typecheck (sandbox-isolated)
├── create_branch (local git workspace)
└── git_commit (local git workspace)

[ DANGEROUS ] (Requires Human Approval Gate)
├── push_branch (pushes to remote origin)
├── create_pull_request (opens PR on upstream GitHub)
├── merge_pull_request (blocked by policy for MVP)
├── delete_branch
└── execute_arbitrary_shell (strictly forbidden)
```

---

## 3. Sandbox Isolation Specifications

When Devaura applies a patch and runs verification checks, the workspace is isolated:

| Parameter | Constraint |
| :--- | :--- |
| **Execution Environment** | Ephemeral container or isolated working directory |
| **Max Execution Duration**| 120 seconds per command |
| **Memory Limit** | 2 GB per sandbox instance |
| **CPU Limit** | 2 vCPUs |
| **Network Access** | Blocked or restricted to approved package registries |
| **Host Filesystem** | Read-only mounts where needed; scratch space wiped on exit |
| **Secret Masking** | Regex-based redaction of JWTs, GitHub PATs, AWS/GCP keys, and Bearer tokens |

---

## 4. Path Traversal & File Access Validation

File operations enforce canonical resolution checks:

```python
def validate_safe_path(base_dir: Path, requested_path: str) -> Path:
    # Resolve absolute canonical paths
    resolved_base = base_dir.resolve()
    target_path = (resolved_base / requested_path).resolve()
    
    # Assert path containment
    if not target_path.is_relative_to(resolved_base):
        raise SecurityViolation(f"Path traversal attempt detected: {requested_path}")
        
    return target_path
```

---

## 5. Audit Logging

Every MCP tool invocation, parameter payload (with secrets redacted), return value, latency, and agent decision is recorded immutably in the `tool_executions` and `investigations` tables for auditability.
