# Devaura MCP Specification & Architecture

## 1. Overview

Model Context Protocol (MCP) is the foundational tool and context interoperability standard within Devaura. Rather than hard-coding proprietary API wrappers, Devaura operates as an **MCP Host**, an **MCP Client**, and exposes a dedicated **Devaura Native MCP Server**.

## 2. Core Capabilities

Devaura's MCP layer provides standard interfaces to:
- Discover external and native MCP servers via `MCPServerRegistry`
- List and introspect tools (`list_tools`) with JSONSchema validation
- List and read resources (`list_resources`, `read_resource`)
- List and hydrate standardized prompts (`list_prompts`, `get_prompt`)
- Invoke tools with comprehensive timeout, cancellation, and execution isolation
- Apply a multi-tier security policy (`SAFE`, `CONTROLLED`, `DANGEROUS`)
- Maintain full audit logging of tool inputs, outputs, latencies, and exit statuses

## 3. Supported Transports

Devaura implements standard MCP transport abstractions:
1. **STDIO Transport**: Process-based communication (`stdin`/`stdout`). Internal logging must strictly route to `stderr` to prevent JSON-RPC protocol corruption.
2. **HTTP / Server-Sent Events (SSE)**: For remote or containerized MCP agents.

## 4. MCP Server Registry

The `MCPServerRegistry` manages connected servers, checks server health, caches tool schemas, and validates parameter schemas against Pydantic models prior to invocation.

```python
class MCPTool(BaseModel):
    server_id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    risk_level: RiskLevel  # SAFE, CONTROLLED, DANGEROUS
    enabled: bool = True
```

## 5. Devaura Native MCP Server Tools

Devaura's built-in MCP server exposes code analysis and maintenance capabilities:

| Tool | Risk Level | Description |
| :--- | :--- | :--- |
| `analyze_repository` | `SAFE` | Scans project structure, languages, dependency manifests, and test frameworks. |
| `search_code` | `SAFE` | Multi-tier code search (AST tokens, exact substring, ripgrep keywords). |
| `read_file` | `SAFE` | Bounded file reading with path traversal guards and line windowing. |
| `git_history` | `SAFE` | Fetches commit history, blame, and diff evolution for relevant symbols. |
| `inspect_diff` | `SAFE` | Computes semantic and line-by-line diffs within a repair workspace. |
| `find_related_tests`| `SAFE` | Discovers unit/integration tests linked to targeted source files. |
| `run_tests` | `CONTROLLED` | Executes tests inside the isolated sandbox. |
| `run_linter` | `CONTROLLED` | Runs flake8, ruff, eslint, or configured linter. |
| `run_typecheck` | `CONTROLLED` | Runs mypy, pyright, tsc. |
| `apply_patch` | `CONTROLLED` | Applies a unified diff patch to an isolated workspace. |
| `create_branch` | `CONTROLLED` | Creates a git branch in the target repository. |
| `git_commit` | `CONTROLLED` | Commits changes in the staged branch. |
| `push_branch` | `DANGEROUS` | Pushes the fix branch to the remote repository (requires explicit approval). |
| `create_pull_request` | `DANGEROUS` | Submits a Pull Request to GitHub (requires explicit approval). |

## 6. MCP Prompts

Standardized prompts defined across the system:
- `debug_issue`: Guides root-cause investigation given an issue description and stack trace.
- `fix_ci_failure`: Synthesizes CI log errors, locates offending commits, and identifies tests.
- `review_pull_request`: Performs secondary independent review of a generated patch.
- `analyze_repository`: Summarizes repository architecture, patterns, and conventions.
