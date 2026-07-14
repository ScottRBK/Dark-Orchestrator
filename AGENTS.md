# DarK Orchestrator

Dark Business needs a reusable service that can schedule, execute, and observe operational scripts.
Those scripts may invoke [AgentShell](https://github.com/ScottRBK/agent-shell) and interact with
Surely CRM, but that business behavior does not belong inside the orchestrator.

## Architecture

```mermaid
flowchart LR
    operator["Operator"] -->|"operates"| dashboard

    subgraph dark["Dark Orchestrator"]
        dashboard["React dashboard<br/>Browser client"] -->|"REST /api"| api
        api["FastAPI application<br/>API, scheduler, services, executor"]
        api -->|"state and migrations"| database[("PostgreSQL<br/>Processes, jobs, runs")]
        api -->|"validate file sources"| scripts["Script root<br/>Filesystem"]
        api -->|"spawn inline or file source"| child["Bash or Python<br/>Child process"]
        child -->|"read file source"| scripts
    end

    child -.->|"optional agent commands"| agentshell["AgentShell"]
    child -.->|"business workflows"| surely["Surely CRM"]
```

- [ADRs](docs/architecture/adr/index.md) are used to track significant changes to the solution.
