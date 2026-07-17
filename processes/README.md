# Process File Root

This is Dark Orchestrator's default root for filesystem-backed process scripts.

Paths entered in the dashboard are relative to this directory. Dark Orchestrator validates and
executes these files but never modifies their content.

To keep workflows in another repository, point the application at that directory:

```bash
DARK_ORCH_SCRIPT_ROOT=/path/to/workflows uv run python main.py
```

A container deployment should mount the selected directory into the application container,
preferably read-only.

## Processes

1. `contact_agent.py` Script to scrape businesses from open street map
