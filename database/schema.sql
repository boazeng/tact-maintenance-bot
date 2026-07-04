-- takt-bots SQLite schema (reference).
-- Tables are auto-created at runtime by database/backends/sqlite/_base.py.
-- Each table stores its primary key plus a `data` column holding the full
-- record as a JSON object (schemaless, mirrors the DynamoDB backend).

CREATE TABLE IF NOT EXISTS bot_scripts (
    script_id TEXT PRIMARY KEY,   -- e.g. "flow_1772177781916"
    data      TEXT NOT NULL       -- JSON: name, active, greeting_*, first_step,
                                  --       steps[], done_actions{}, _flow_positions{}, timestamps
);

CREATE TABLE IF NOT EXISTS sessions (
    phone TEXT PRIMARY KEY,        -- "972501234567"
    data  TEXT NOT NULL            -- JSON: session_id, script_id, step, status,
                                  --       expires_at, collected save_to fields, session_log[]
);

CREATE TABLE IF NOT EXISTS service_calls (
    id   TEXT PRIMARY KEY,         -- UUID
    data TEXT NOT NULL             -- JSON: phone, name, issue_type, description, urgency,
                                  --       status, fault_text, optional Priority passthrough fields
);

CREATE TABLE IF NOT EXISTS messages (
    id   TEXT PRIMARY KEY,         -- UUID
    data TEXT NOT NULL             -- JSON: phone, name, text, msg_type, status, parsed_data
);

CREATE TABLE IF NOT EXISTS bot_prompts (
    prompt_id TEXT PRIMARY KEY,
    data      TEXT NOT NULL        -- JSON: active, prompt text, timestamps
);
