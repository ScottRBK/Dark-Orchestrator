# ADR-002: Inline and Filesystem Process Sources

- **Status:** Accepted
- **Date:** 2026-07-13
- **Extends:** [ADR-001](adr1_dark_orchestrator.md)

## Context

ADR-001 stored every process script inline in PostgreSQL. That is appropriate for small scripts
created and managed in Dark Orchestrator, but substantial business workflows are normally managed as
version-controlled files outside the application.

Dark Orchestrator needs to distinguish these ownership models without treating a path as script
content or allowing the dashboard to become a source-code editor for externally managed files.

The word "host" is deployment-dependent. When the application runs in a container, its host
filesystem is the container filesystem and any external directory must be mounted into it.
Therefore, the domain uses `file`; the dashboard presents that source as **Host file**.

## Decision

A process has exactly one discriminated source:

```json
{
  "kind": "inline",
  "content": "print('managed by Dark')"
}
```

or:

```json
{
  "kind": "file",
  "path": "customer-onboarding/run.py"
}
```

Pydantic discriminates the source union using `kind`, so an inline source cannot contain a path and
a file source cannot contain inline content.

### Inline sources

- Content is stored in PostgreSQL.
- Content can be created and edited through the API and dashboard.
- Bash content executes with `bash -c`.
- Python content executes with the interpreter running Dark Orchestrator and `-c`.

### File sources

- PostgreSQL stores only a path relative to `SCRIPT_ROOT`.
- `DARK_ORCH_SCRIPT_ROOT` configures that root.
- The default root is the repository's `processes` directory.
- The dashboard can change the reference but never reads, copies, or modifies file content.
- Bash files execute by passing the resolved path to Bash.
- Python files execute by passing the resolved path to the Python interpreter.
- The configured script root is the child process working directory.

A file therefore does not need an executable permission bit. Its selected process type determines
the interpreter.

### Path validation

Dark Orchestrator validates a file source when it is created, when its path is updated, and again
immediately before every run.

A valid file source must:

1. be a relative path;
2. contain no parent-directory traversal;
3. resolve beneath the configured script root after following symbolic links;
4. resolve to an existing regular file; and
5. be readable by the orchestrator operating-system user.

Absolute paths and symbolic links escaping the script root are rejected. Revalidation at execution
time handles files that were removed, replaced, or made unreadable after process creation. Such a
failure becomes a normal persisted error run.

This boundary reduces accidental filesystem exposure. Process scripts are still privileged arbitrary
code and must be trusted.

### Persistence

The `processes` table has these source columns:

| Column | Inline source | File source |
|---|---:|---:|
| `source_kind` | `inline` | `file` |
| `script` | content | `NULL` |
| `script_path` | `NULL` | relative path |

A PostgreSQL check constraint guarantees exactly one valid representation. Migration
`002_process_sources.sql` classifies every existing process as `inline`, preserving its script
content and behavior.

### API and dashboard

Process create, update, and response models use the nested `source` object. The previous flat
`script` request and response field is replaced rather than overloaded with two meanings.

Process cards display both dimensions independently:

- process interpreter: **Python** or **Bash**;
- source ownership: **Inline** or **Host file**; and
- inline first-line preview or relative file path.

The process form uses a source selector. Inline mode displays the script editor. Host-file mode
displays only the relative path and states that the file is managed outside Dark Orchestrator.

## Consequences

### Benefits

- Small scripts remain easy to manage from the dashboard.
- Substantial workflows can remain in Git and use ordinary review and deployment practices.
- The API makes source ownership explicit and prevents ambiguous `script` values.
- Relative paths make deployments movable between machines and containers.
- A constrained root limits accidental access to unrelated host files.
- Existing inline processes migrate without manual changes.

### Trade-offs and limits

- File content can change between runs without a process record changing.
- Run history does not yet store a source checksum or immutable revision.
- A missing or unreadable file prevents execution but does not automatically disable its process.
- Every scheduler instance must see the same script root and file contents.
- Container deployments must mount the configured root, preferably read-only.
- File availability is validated by the API and executor but is not continuously monitored.
- Relative arguments and data files resolve from the configured script root.

## Alternatives considered

### Store content and paths in the same `script` field

Rejected because every consumer would need to infer the field's meaning from another value. Separate
columns and a discriminated API make invalid states visible and constrain them in PostgreSQL.

### Allow arbitrary absolute paths

Rejected because it would expose the entire filesystem namespace and make process definitions tied
to one machine.

### Edit host files from the dashboard

Rejected because Dark Orchestrator would compete with Git or another external owner as the source of
truth.

### Copy file content into PostgreSQL before execution

Rejected because it silently changes a live file reference into a snapshot and obscures which source
owns updates. Immutable run provenance can be designed separately.
