ALTER TABLE processes
    ADD COLUMN source_kind VARCHAR(20) NOT NULL DEFAULT 'inline',
    ADD COLUMN script_path TEXT,
    ALTER COLUMN script DROP NOT NULL;

ALTER TABLE processes
    ADD CONSTRAINT process_has_exactly_one_source CHECK (
        (
            source_kind = 'inline'
            AND script IS NOT NULL
            AND script_path IS NULL
        )
        OR
        (
            source_kind = 'file'
            AND script IS NULL
            AND script_path IS NOT NULL
        )
    );
