# Dark Orchestrator

Dark Orchestrator schedules, executes, and observes the processes that run Dark Business. It is a
generic orchestration layer: business workflows live in scripts and use tools such as AgentShell and
the Surely CRM client.

## Capabilities

- FastAPI REST API with automatic OpenAPI documentation
- JSON-first Python CLI for the complete REST API
- PostgreSQL persistence and ordered SQL migrations
- Bash and Python process execution
- Inline scripts and filesystem-backed scripts beneath a configured root
- One-off jobs, future schedules, and strict five-field cron schedules
- Start, pause, resume, and stop controls
- Atomic PostgreSQL job claiming to prevent duplicate dispatch
- Captured output, timeout handling, process-tree cleanup, and failure history
- Responsive React and TypeScript mission-control dashboard
- Real PostgreSQL integration tests and Playwright browser tests

## Run locally

Prerequisites:

- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- Node.js 22 and npm
- Docker

Start PostgreSQL and install the locked dependencies:

```bash
docker compose up -d --wait postgres
uv sync
cd web
npm ci --ignore-scripts
npm run build
cd ..
```

Start the application:

```bash
uv run python main.py
```

Open <http://127.0.0.1:8099>. API documentation is available at
<http://127.0.0.1:8099/docs>.

Database migrations run automatically during application startup.

## Command-line client

Run the CLI directly from the repository:

```bash
./dark-orchestrator health
```

To make it available on `PATH`, symlink the checkout executable:

```bash
mkdir -p "$HOME/.local/bin"
ln -s "$(pwd)/dark-orchestrator" "$HOME/.local/bin/dark-orchestrator"
```

The server defaults to <http://127.0.0.1:8099>. `--url` overrides `DARK_ORCH_API_URL`, which
overrides that default.

```bash
dark-orchestrator --url http://127.0.0.1:8099 orchestrator status

dark-orchestrator process create \
  --name "Daily report" \
  --type python \
  --inline "print('ready')"

dark-orchestrator process create \
  --name "Host workflow" \
  --type bash \
  --file workflows/run.sh

dark-orchestrator job create \
  --process-id 4ee6f8f6-0280-4f8e-a1bc-8d056ec8df10 \
  --recurring \
  --cron "*/5 * * * *"

dark-orchestrator job create \
  --process-id 4ee6f8f6-0280-4f8e-a1bc-8d056ec8df10 \
  -- --campaign-location "Leeds, England"

dark-orchestrator run list --limit 25
```

A `--file` value is relative to the server's `SCRIPT_ROOT`; it does not upload a local file.
Successful response bodies are JSON on standard output. HTTP and network failures are JSON on
standard error and return a non-zero exit status. Use `dark-orchestrator --help` and each command's
`--help` option for the complete command surface.

## Frontend development

Run the API and Vite development server in separate terminals:

```bash
uv run python main.py
```

```bash
cd web
npm run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api` to port `8099` during development. The production
Vite build is served directly by FastAPI.

## Tests

See the [test strategy](docs/test-strategy.md) for the approach, test boundaries, and database
isolation.

CLI tests live under `tests/cli/` and are included in the normal pytest suite. They invoke the real
executable against a temporary Uvicorn server and the isolated backend-test database.

The backend and browser-test databases are separate from the development database and are reset
before use. Run the complete suite with:

```bash
docker compose up -d --wait postgres
cd web
npm ci --ignore-scripts
npm run build
cd ..
uv run pytest
cd web
npm run test:e2e
```

The backend suite tests only through the HTTP API, using real PostgreSQL and real harmless child
processes. Playwright drives the dashboard in a real Chromium browser against the real API. If its
browser is not already cached, install it once with:

```bash
cd web
npx playwright install chromium
```

## Process model

A process selects a Python or Bash interpreter and one script source:

- **Inline** content is stored in PostgreSQL and editable through Dark Orchestrator.
- **Host file** paths are relative to `SCRIPT_ROOT` and managed outside Dark Orchestrator.

File sources must resolve to readable regular files beneath the configured root. Absolute paths,
parent traversal, and symbolic links escaping the root are rejected. Files are validated when a
process is created or updated and again before each run. The default root is
[`processes`](processes/README.md).

Python executes with the interpreter running Dark Orchestrator, and Bash executes with Bash.
AgentShell agents can be invoked by placing the relevant `agent-shell` command in either source.

A job schedules a process and may provide a fixed list of command-line arguments. One-off jobs run
immediately unless `next_run_at` is supplied. Recurring jobs require a strict five-field cron
expression. All dates crossing the API must include a timezone and are normalized to UTC. In the
CLI, arguments after `--` are passed to the process unchanged.

## API overview

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/health` | Service, database, and scheduler health |
| `GET` | `/api/orchestrator` | Scheduler status |
| `POST` | `/api/orchestrator/{start,pause,stop}` | Control dispatch |
| `GET/POST` | `/api/processes` | List or create processes |
| `GET/PATCH/DELETE` | `/api/processes/{id}` | Manage a process |
| `POST` | `/api/processes/{id}/{enable,disable}` | Control process eligibility |
| `GET/POST` | `/api/jobs` | List or create jobs |
| `GET/PATCH/DELETE` | `/api/jobs/{id}` | Manage a job |
| `POST` | `/api/jobs/{id}/run-now` | Queue an immediate run |
| `GET` | `/api/runs` | Read run history and captured output |

## Configuration

Settings use the `DARK_ORCH_` environment prefix and may be placed in `.env`.

| Setting | Default |
|---|---|
| `HOST` | `127.0.0.1` |
| `PORT` | `8099` |
| `DATABASE_URL` | Local Compose PostgreSQL on port `54329` |
| `HEART_BEAT_INTERVAL` | `30` seconds |
| `MAX_CONCURRENT_JOBS` | `4` |
| `PROCESS_TIMEOUT_SECONDS` | `900` |
| `MAX_CAPTURED_OUTPUT_BYTES` | `1000000` |
| `SCRIPT_ROOT` | Repository `processes` directory |
| `CORS_ORIGINS` | `http://localhost:5173` |

## Security

Processes execute arbitrary local code by design. The server binds only to loopback by default. Do
not expose it to an untrusted network until authentication and authorization have been added at the
API boundary. Run the service as an unprivileged operating-system user and treat process scripts as
privileged configuration.

The dependency audit is recorded in
[`docs/dependency-audit.md`](docs/dependency-audit.md).

## Business integration boundary

Dark Orchestrator does not duplicate CRM state or hard-code lead-generation workflows. Those flows
are scheduled processes which read and update Surely CRM. This keeps the orchestrator reusable.

The implemented architecture and explicit v1 boundaries are recorded in
[`ADR-001`](docs/architecture/adr/adr1_dark_orchestrator.md). Script source ownership and filesystem
security are recorded in [`ADR-002`](docs/architecture/adr/adr2_process_script_sources.md). The
JSON-first CLI contract is recorded in
[`ADR-003`](docs/architecture/adr/adr3_command_line_client.md).
