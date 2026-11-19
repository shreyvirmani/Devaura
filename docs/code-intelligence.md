# Devaura — Code Intelligence Layer (Phase 3)

> **Tagline:** From failure to verified fix.
> **Layer:** Deterministic Code Intelligence, AST Parsing, Multi-Tier Search, and Repository Knowledge Graph.

---

## 1. Overview

The **Code Intelligence Layer** equips Devaura with structured, deterministic understanding of repository codebases. Rather than treating code as raw unstructured text or relying on stochastic LLM queries to guess where functions live, Devaura extracts concrete structural facts:

- **Where is a symbol defined and what is its signature?**
- **Which functions call this function and which does it call?**
- **Which classes inherit or extend other classes?**
- **Which internal files or external modules are imported?**
- **Which test files and test functions verify which source components?**
- **Which files change together historically in Git commits?**
- **What is the blast radius if a function or class is modified?**

---

## 2. Architecture & Components

```text
                               DEVAURA CODE INTELLIGENCE
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
            AST Parsers            Multi-Tier Search       Repository Graph
                    │                      │                      │
          ┌─────────┴─────────┐    ┌───────┴───────┐      ┌───────┴───────┐
          │ PythonASTParser   │    │ Tier 1: Ripgrep│     │ Directed Graph│
          │ JavaScriptParser  │    │ Tier 2: Symbol │     │ Call Chains   │
          │ TypeScriptParser  │    │ Tier 3: Path   │     │ Inheritance   │
          │ ParserRegistry    │    │ Tier 4: Semantic│    │ Test Mappings │
          └───────────────────┘    └───────────────┘      └───────────────┘
                                           │
                                  Repository Indexer
                                  (Full & Incremental)
                                           │
                          ┌────────────────┴────────────────┐
                          │                                 │
                   SQLAlchemy Models                Native MCP Server
                   (code_files, etc.)              (index_repository, etc.)
```

---

## 3. Subsystems

### 3.1 AST Parsers (`code_intelligence/parsers/`)
- `base.py`: Abstract `BaseParser` interface producing `ParsedFile`, `ParsedSymbol`, and `ParsedImport`.
- `python_parser.py`: Standard library `ast`-based parser extracting classes, functions, async functions, methods, signatures, docstrings, nested scopes, function calls, base class inheritance (`extends`), and internal/external imports.
- `javascript_parser.py`: Deterministic parser for `.js`, `.jsx`, `.mjs`, `.cjs` files extracting ES6 imports, CommonJS `require()`, classes, methods, arrow functions, and async routines.
- `typescript_parser.py`: Extends JavaScript parsing with TypeScript interfaces, type aliases, and type-annotated method signatures.
- `registry.py`: Singleton `default_parser_registry` mapping file extensions to language parsers.

### 3.2 Multi-Tier Search Engine (`code_intelligence/search/`)
- **Tier 1 (Ripgrep Search)**: High-performance substring and regex matching via `rg` CLI with fallback to an optimized Python file walker. Respects `.gitignore` and ignores noisy directories (`node_modules`, `.venv`, `.git`, `__pycache__`).
- **Tier 2 (Symbol Search)**: Symbol-aware search querying indexed AST records by name, qualified name, or symbol kind (`class`, `method`, `function`, `interface`).
- **Tier 3 (Path Search)**: Fast path globbing and substring matching for repository file navigation.
- **Tier 4 (Semantic Search)**: Clean pluggable vector search abstraction (gracefully disabled when no embeddings model is configured).
- **Coordinator**: `MultiTierSearchCoordinator` queries requested tiers, deduplicates matches, and ranks results by confidence score.

### 3.3 Repository Knowledge Graph (`code_intelligence/graph/`)
- `repository_graph.py`: In-memory directed graph supporting BFS pathfinding, inbound/outbound edge queries, and dependency tracking.
- `relationship_builder.py`: Resolves semantic relationships:
  - `CONTAINS`: File contains top-level symbol.
  - `DEFINES`: Parent class defines method or member.
  - `IMPORTS`: File imports module or symbol (intra-repo resolved to file node, external to module node).
  - `CALLS`: Function or method calls another symbol.
  - `EXTENDS`: Subclass inherits from superclass.
  - `TESTS`: Test file or function targets implementation source.
- `queries.py`: `GraphQueryEngine` providing `get_callers`, `get_callees`, `get_file_dependencies`, and `get_blast_radius`.

### 3.4 Test Relationships Engine (`code_intelligence/tests/`)
- `test_relationships.py`: Detects source-to-test mappings using:
  1. File naming conventions (`test_<name>.py`, `<name>_test.py`, `<name>.test.ts`, `<name>.spec.ts`).
  2. Import tracing (test files importing source modules).
  3. Function-level heuristic matching (`test_add` -> `add`, `test_calculator_divide` -> `Calculator.divide`).

### 3.5 Git Intelligence (`code_intelligence/git/`)
- `git_intelligence.py`:
  - `get_commit_history`: Fetches commits affecting a specific file or workspace with author attribution and date formatting.
  - `get_file_blame`: Line-by-line blame attribution.
  - `get_change_co_occurrence`: Analyzes commit history to compute which files frequently change together with confidence scores.

### 3.6 Indexing Pipeline (`code_intelligence/indexer/`)
- `file_indexer.py`: Scans workspaces, detects file content hashes (SHA-256), and parses files.
- `symbol_indexer.py`: Persists file, symbol, import, graph edge, and test mapping records to SQLite/PostgreSQL.
- `repository_indexer.py`: High-level coordinator supporting both full re-indexing and fast incremental indexing (skipping unchanged file hashes).

---

## 4. MCP Server Integration

The native Devaura MCP server (`mcp/server/devaura_server.py`) exposes Code Intelligence tools:

| MCP Tool | Risk Level | Description |
|---|---|---|
| `search_code` | SAFE | Multi-tier code search using ripgrep with fallback |
| `index_repository` | SAFE | Triggers full/incremental deterministic AST indexing |
| `search_symbol` | SAFE | Searches indexed symbols by query and kind |
| `get_symbol` | SAFE | Retrieves symbol definition, signature, and docstring |
| `get_relationships` | SAFE | Retrieves callers, callees, imports, and dependents |
| `get_repository_graph` | SAFE | Generates complete graph summary (nodes, edges, stats) |
| `find_related_tests` | SAFE | Finds related tests using AST intelligence & naming patterns |

---

## 5. REST API Surface (`/api/v1/code-intelligence/`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/index` | Triggers indexing for a repository or workspace |
| `GET` | `/status/{repository_id}` | Retrieves indexing status and aggregate statistics |
| `GET` | `/files/{repository_id}` | Lists indexed files with language and metrics |
| `GET` | `/symbols/{repository_id}` | Lists/filters symbols by file, kind, or search query |
| `GET` | `/symbols/{repository_id}/{symbol_id}` | Detailed symbol info with callers & callees |
| `POST` | `/search` | Executes multi-tier search across Ripgrep, Symbol, and Path |
| `GET` | `/graph/{repository_id}` | Returns graph nodes, edges, and relationship statistics |
| `GET` | `/tests/{repository_id}` | Returns discovered test-to-source mappings |
| `GET` | `/git/history` | Retrieves Git commit history with author attribution |
| `GET` | `/git/blame` | Retrieves Git blame for a file line range |
| `GET` | `/git/co-occurrence` | Retrieves files that co-change with a target file |

---

## 6. Database Schema

The Code Intelligence layer adds 6 relational tables under `database/models/code_intelligence.py`:

1. `code_files`: Stores file paths, language, SHA-256 hash, line count, and byte size.
2. `code_symbols`: Stores AST symbols, signatures, docstrings, line numbers, and parent pointers.
3. `code_relationships`: Stores graph edges (`CONTAINS`, `DEFINES`, `IMPORTS`, `CALLS`, `EXTENDS`, `TESTS`) with confidence ratings.
4. `code_imports`: Stores imported modules, symbols, aliases, and external vs intra-repo flags.
5. `code_index_runs`: Audit trail of indexing runs, file/symbol counts, status, and duration.
6. `code_test_mappings`: Bidirectional links between test files and source implementation files.
