-- Migration: Add messages table for conversation search (Phase 3.6)
--
-- Stores conversation messages for search and recall.
-- Supports:
-- - Full-text search (FTS) via tsvector index
-- - Vector similarity search (optional embeddings)
-- - Role-based filtering (user/assistant/tool)
-- - Temporal filtering by created_at
-- - Session isolation
--
-- Run with:
--   psql $AGENTICA_POSTGRES_URL -f scripts/migrations/004_add_messages_table.sql

BEGIN;

-- ============================================================================
-- memory_messages table
-- ============================================================================

CREATE TABLE IF NOT EXISTS memory_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    agent_id TEXT,
    content TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'tool')),
    embedding vector(4096),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for session filtering (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_messages_session ON memory_messages(session_id);

-- Index for temporal queries (ORDER BY created_at DESC)
CREATE INDEX IF NOT EXISTS idx_messages_created ON memory_messages(created_at DESC);

-- Composite index for session + role filtering
CREATE INDEX IF NOT EXISTS idx_messages_session_role ON memory_messages(session_id, role);

-- Full-text search index using GIN
-- This enables efficient plainto_tsquery searches
CREATE INDEX IF NOT EXISTS idx_messages_content_fts ON memory_messages
    USING gin(to_tsvector('english', content));

-- Optional: Vector index for semantic search (uncomment if heavily used)
-- CREATE INDEX IF NOT EXISTS idx_messages_embedding ON memory_messages
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

COMMIT;

-- Verification queries (run manually to confirm migration)
-- \d memory_messages
-- \di idx_messages_*
