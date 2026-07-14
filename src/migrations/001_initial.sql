CREATE TABLE processes (
    process_id UUID PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('bash', 'python')),
    name VARCHAR(120) NOT NULL,
    script TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    created_by VARCHAR(120) NOT NULL,
    modified_at TIMESTAMPTZ NOT NULL,
    modified_by VARCHAR(120) NOT NULL,
    last_run_at TIMESTAMPTZ
);

CREATE TABLE jobs (
    job_id UUID PRIMARY KEY,
    process_id UUID NOT NULL REFERENCES processes(process_id),
    recurring BOOLEAN NOT NULL DEFAULT FALSE,
    cron VARCHAR(120),
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    created_by VARCHAR(120) NOT NULL,
    modified_at TIMESTAMPTZ NOT NULL,
    modified_by VARCHAR(120) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT recurring_job_requires_cron CHECK (
        (recurring AND cron IS NOT NULL) OR (NOT recurring AND cron IS NULL)
    )
);

CREATE TABLE job_runs (
    job_run_id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs(job_id),
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'active', 'completed', 'error')
    ),
    captured_output TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE TABLE job_exceptions (
    job_exception_id UUID PRIMARY KEY,
    job_run_id UUID NOT NULL UNIQUE REFERENCES job_runs(job_run_id),
    exception TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX jobs_due_idx ON jobs(next_run_at) WHERE active;
CREATE INDEX job_runs_job_started_idx ON job_runs(job_id, started_at DESC);
CREATE INDEX job_runs_status_idx ON job_runs(status);
