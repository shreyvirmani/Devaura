# Devaura Local Development Guide

## 1. Prerequisites

- **Python**: 3.12+
- **Node.js**: 20.x or 22.x LTS (with `npm`)
- **Git**: 2.40+
- **Docker**: (Optional for local containerized execution, fallback to local workspace runner)
- **PostgreSQL**: 15+ (SQLite supported seamlessly for local development and unit tests)

---

## 2. Directory Structure

```
devaura/
├── apps/
│   ├── api/                   # FastAPI Backend
│   └── web/                   # Next.js Frontend
├── agent/                     # Core Agent Orchestrator & Phases
│   ├── orchestrator/
│   ├── investigator/
│   ├── planner/
│   ├── repair/
│   ├── verifier/
│   └── reviewer/
├── mcp/                       # MCP Client, Native Server & Registry
│   ├── client/
│   ├── registry/
│   ├── policy/
│   └── server/
├── integrations/              # Platform integrations (GitHub, CI/CD)
│   └── github/
├── code_intelligence/         # AST, ripgrep search, dependency graph, git
├── sandbox/                   # Isolated execution environment & docker
├── database/                  # SQLAlchemy/SQLModel models and migrations
├── evaluation/                # Benchmarks, test datasets, and eval harness
├── tests/                     # Unit, integration, and E2E test suites
├── docs/                      # Technical specifications & documentation
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 3. Quickstart

### 3.1 Backend Setup

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r apps/api/requirements.txt

# Copy environment template
cp .env.example .env

# Run API server
uvicorn apps.api.main:app --reload --port 8000
```

### 3.2 Frontend Setup

```bash
cd apps/web
npm install
npm run dev
```

The web dashboard is accessible at `http://localhost:3000` and the API documentation at `http://localhost:8000/docs`.

---

## 4. Running Tests

```bash
# Run all unit tests
pytest -v

# Run with coverage report
pytest --cov=agent --cov=mcp --cov=database tests/
```
