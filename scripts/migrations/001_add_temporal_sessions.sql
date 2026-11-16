-- Migration: Add temporal_sessions table
-- Purpose: Store session-level summaries from handoffs with embeddings
--
-- This enables session-level semantic search:
-- - "Find sessions where we chose PostgreSQL"
-- - "What sessions had authentication issues?"
--
-- Links to temporal_facts via session_id for fact-level detail.

-- Ensure pgvector is available
CREATE EXTENSION IF NOT EXISTS vector;

-- Create temporal_sessions table
CREATE TABLE IF NOT EXISTS temporal_sessions (
    -- Primary key: session_id from handoffs/facts
    session_id TEXT PRIMARY KEY,

    -- Session metadata
    session_name TEXT,

    -- Content from handoffs (for embedding)
    summary TEXT,              -- task_summary
    key_decisions TEXT,        -- design decisions with rationale
    what_worked TEXT,          -- successful patterns
    what_failed TEXT,          -- failure modes
    outcome TEXT CHECK(outcome IN ('SUCCEEDED', 'PARTIAL_PLUS', 'PARTIAL_MINUS', 'FAILED', 'UNKNOWN')),

    -- Braintrust correlation
    root_span_id TEXT,         -- For linking to Braintrust traces

    -- Composite embedding of summary + decisions + worked + failed
    -- Using 1024 dims (native Voyage dimension, no padding needed)
    embedding vector(1024),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- HNSW index for cosine similarity search (1024 dims within limit)
-- Create AFTER initial data load for better index quality:
-- CREATE INDEX idx_temporal_sessions_embedding_hnsw
--     ON temporal_sessions
--     USING hnsw (embedding vector_cosine_ops)
--     WITH (m = 16, ef_construction = 64);

-- Full-text search on summary
CREATE INDEX IF NOT EXISTS idx_temporal_sessions_summary_fts
    ON temporal_sessions
    USING gin(to_tsvector('english', COALESCE(summary, '')));

-- Index for outcome filtering
CREATE INDEX IF NOT EXISTS idx_temporal_sessions_outcome
    ON temporal_sessions(outcome);

-- Index for session_name lookup
CREATE INDEX IF NOT EXISTS idx_temporal_sessions_name
    ON temporal_sessions(session_name);

-- Comment for documentation
COMMENT ON TABLE temporal_sessions IS 'Session-level summaries from handoffs with embeddings for semantic search';
COMMENT ON COLUMN temporal_sessions.embedding IS 'Voyage code-3 embedding (1024 dims native) of combined summary + decisions + worked + failed';
