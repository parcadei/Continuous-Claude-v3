-- Session tree schema for branching
-- Location: .claude/cache/agentica-memory/memory.db (shared with MemoryService)

-- Session entries table with UUID-linked tree structure
CREATE TABLE IF NOT EXISTS session_entries (
    id TEXT PRIMARY KEY,           -- UUID-based: "se-{uuid8}"
    session_id TEXT NOT NULL,      -- Parent session (from CoordinationDB)
    branch_id TEXT,                -- Which branch this entry belongs to
    type TEXT NOT NULL CHECK(type IN ('session', 'message', 'branch', 'model_change')),
    parent_id TEXT,                -- NULL for root session, otherwise parent entry ID
    timestamp REAL NOT NULL,

    -- Session-specific
    cwd TEXT,
    provider TEXT,
    model_id TEXT,

    -- Message-specific
    role TEXT,                     -- user, assistant, toolResult
    content TEXT,
    usage_json TEXT,               -- Token usage stats

    -- Branch-specific
    branch_name TEXT,              -- Human-readable branch name
    branch_description TEXT,       -- Why this branch was created

    FOREIGN KEY (parent_id) REFERENCES session_entries(id)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_session_entries_session ON session_entries(session_id);
CREATE INDEX IF NOT EXISTS idx_session_entries_parent ON session_entries(parent_id);
CREATE INDEX IF NOT EXISTS idx_session_entries_type ON session_entries(type);
CREATE INDEX IF NOT EXISTS idx_session_entries_timestamp ON session_entries(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_session_entries_branch ON session_entries(branch_id);

-- View for branch hierarchy (recursive CTE)
CREATE VIEW IF NOT EXISTS branch_tree AS
WITH RECURSIVE tree AS (
    SELECT id, parent_id, type, branch_name, session_id, 0 as depth
    FROM session_entries
    WHERE type = 'session' AND parent_id IS NULL

    UNION ALL

    SELECT e.id, e.parent_id, e.type, e.branch_name, e.session_id, t.depth + 1
    FROM session_entries e
    JOIN tree t ON e.parent_id = t.id
    WHERE t.depth < 100  -- Prevent infinite recursion
)
SELECT * FROM tree WHERE type = 'branch';

-- Branches table for quick branch listing
CREATE TABLE IF NOT EXISTS branches (
    id TEXT PRIMARY KEY,           -- Same as session_entries.id for branch
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    parent_branch_id TEXT,         -- NULL for main branch
    fork_point_id TEXT,            -- Entry ID where branch was forked from
    created_at REAL NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,

    FOREIGN KEY (parent_branch_id) REFERENCES branches(id),
    FOREIGN KEY (fork_point_id) REFERENCES session_entries(id)
);

CREATE INDEX IF NOT EXISTS idx_branches_session ON branches(session_id);
CREATE INDEX IF NOT EXISTS idx_branches_active ON branches(session_id, is_active);
