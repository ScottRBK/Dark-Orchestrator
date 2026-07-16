# Test Strategy

## Overall approach

Dark Orchestrator uses an **integration-first** test strategy.

We prefer testing real user-facing boundaries over testing small functions in isolation. This gives
us confidence that the components work together correctly.

There are three main test groups.

## Backend integration tests

These tests call the real FastAPI application using `TestClient`.

They exercise:

- API routes;
- application services;
- PostgreSQL queries and migrations;
- scheduling and orchestration;
- script execution; and
- filesystem handling.

PostgreSQL is real, and scripts run as real child processes.

The only shortcut is that `TestClient` calls the application without opening a network socket.

Examples include:

- creating processes and jobs;
- claiming scheduled jobs;
- preventing overlapping runs;
- capturing script output;
- validating file paths; and
- applying database migrations.

## CLI end-to-end tests

These tests start the actual server and run the CLI as a separate process.

The full path is:

```text
CLI process → real HTTP socket → Uvicorn → FastAPI → PostgreSQL
```

They verify that a user can:

- create and manage processes;
- create and run jobs;
- inspect run history;
- control the orchestrator;
- select a server using configuration; and
- receive useful JSON errors.

Purely local CLI behaviour, such as `--help` and invalid arguments, does not need a server.

## Browser end-to-end tests

Playwright opens the real React application in a browser.

The full path is:

```text
Browser → React application → HTTP API → FastAPI → PostgreSQL
```

These tests cover the most important dashboard workflows, including creating and running processes
and controlling the orchestrator.

## Database isolation

Tests never use the development database.

| Usage | Database |
|---|---|
| Development | `dark_orchestrator` |
| Pytest, including CLI tests | `dark_orchestrator_test` |
| Playwright | `dark_orchestrator_e2e` |

The Pytest database schema is rebuilt before every test.

The Playwright database is reset before the browser suite starts.

## Regression testing

When we find a bug, we add or improve a test that reproduces it through the closest public boundary.

For example, the overlapping-job problem is tested through the API with a real scheduler, database
and child process. This verifies the complete behaviour rather than only testing the SQL or a helper
function.

## Running the tests

Run all Python and CLI tests:

```bash
uv run pytest
```

Run the browser tests separately:

```bash
cd web
npm run test:e2e
```

There are currently no conventional unit tests. That is intentional: the project is small enough
that testing through real boundaries provides more useful confidence.
