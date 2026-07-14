# ADR-003: Command-Line REST Client

- **Status:** Accepted
- **Date:** 2026-07-14
- **Scope:** Python command-line client for the existing REST API

## Context

ADR-001 established the REST API as Dark Orchestrator's public application boundary and deferred a
command-line client. Dark Business also envisages AI agents operating Dark Orchestrator through a
CLI, with agent skills supplying usage guidance separately.

The API already exposes health, scheduler controls, process management, job management, and run
history. A CLI does not require another server route, direct database access, or changes to the
scheduler.

The client must be suitable for automation. Its output and exit status therefore matter more than
interactive formatting. The project is not currently structured as an installable Python package,
and introducing packaging solely for this client would require an unrelated source-layout change or
another build dependency.

## Decision

### Boundary

`dark-orchestrator` is a Python executable in the repository root. It delegates to `src/cli.py`,
which owns argument parsing, HTTP requests, and terminal output.

The client communicates only with `/api` over JSON/REST. It does not import application services,
construct `Server`, or access PostgreSQL. The server remains responsible for domain validation and
all orchestration behavior.

A process file source remains a path relative to the server's configured `SCRIPT_ROOT`. The CLI
sends that path as JSON; it does not read or upload a client-side file.

### Command surface

The CLI represents the complete current REST surface:

```text
dark-orchestrator health

dark-orchestrator orchestrator {status,start,pause,stop}

dark-orchestrator process {list,get,create,update,enable,disable,delete}

dark-orchestrator job {list,get,create,update,run-now,delete}

dark-orchestrator run list [--job-id UUID] [--limit NUMBER]
```

Process creation and updates accept either `--inline` content or a server-relative `--file` path.
Job creation supports one-off and recurring schedules. Job updates support activation state and the
next run time.

### Configuration and automation contract

The API base URL is selected in this order:

1. the global `--url` option;
2. `DARK_ORCH_API_URL`; and
3. `http://127.0.0.1:8099`.

Successful response bodies are pretty-printed JSON on standard output. A successful HTTP `204`
produces no output. HTTP, network, and invalid-response errors are JSON on standard error and return
exit status `1`. Command usage errors use argparse's standard error output and exit status `2`.

There are no prompts, tables, colors, configuration profiles, or authentication options in this
slice.

### Dependencies and distribution

The implementation uses only Python's standard library. No runtime package was added and no
supply-chain change was required.

The executable can be run from a checkout or symlinked into a directory on `PATH`. Building and
publishing an installable wheel is deferred until the repository has a genuine need for package
distribution.

### Validation

CLI contract tests invoke the real executable as a subprocess and communicate with a real local HTTP
socket. A small deterministic HTTP server supplies API responses and records requests. Tests observe
only arguments, exit status, standard output, standard error, and HTTP requests.

These tests verify command parsing, request mapping, JSON serialization, and error behavior without
PostgreSQL or Docker. A full CLI-to-FastAPI-to-PostgreSQL integration suite is explicitly deferred
to a separate slice of work. Existing backend integration tests continue to verify API behavior
through FastAPI and real PostgreSQL.

Agent skills are also deferred. They will consume this public CLI contract rather than bypassing it
with direct database or service access.

## Consequences

### Benefits

- Agents and shell automation receive a stable JSON-first interface.
- The CLI remains independent from backend implementation details.
- Every existing REST capability is available without falling back to ad hoc `curl` commands.
- The client adds no runtime dependency or supply-chain surface.
- CLI tests run quickly without application infrastructure.

### Trade-offs

- Contract tests do not yet prove the complete CLI-to-live-server path.
- The executable is distributed from a source checkout rather than as an installed Python package.
- The CLI mirrors the current API and must evolve when that public contract changes.
- There is still no authentication or authorization.
- Agent skill instructions are not included in this slice.

## Deferred decisions

1. Full-stack CLI integration tests using an isolated database lifecycle.
2. An agent skill for operating Dark Orchestrator through the CLI.
3. Installable package or standalone binary distribution.
4. Authentication and credential configuration.
