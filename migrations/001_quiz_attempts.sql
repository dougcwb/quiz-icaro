CREATE TABLE IF NOT EXISTS quiz_attempts (
    attempt_id UUID PRIMARY KEY,
    player_name TEXT NOT NULL,
    quiz_id TEXT NOT NULL,
    question_data JSONB NOT NULL,
    answer_log JSONB NOT NULL DEFAULT '[]'::jsonb,
    pending_choices JSONB NOT NULL DEFAULT '[]'::jsonb,
    score INTEGER NOT NULL DEFAULT 0 CHECK (score >= 0),
    combo INTEGER NOT NULL DEFAULT 0 CHECK (combo >= 0),
    errors INTEGER NOT NULL DEFAULT 0 CHECK (errors >= 0),
    correct_count INTEGER NOT NULL DEFAULT 0 CHECK (correct_count >= 0),
    first_try_correct JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_response JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS quiz_attempts_created_at_idx
    ON quiz_attempts (created_at);
