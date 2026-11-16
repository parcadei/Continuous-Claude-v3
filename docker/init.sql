-- PostgreSQL + pgvector initialization script for Agentica Memory Service
-- This script runs on container creation to set up the memory schema.

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Memory schema
-- Core memory (key-value blocks per session/agent)
CREATE TABLE core_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    agent_id TEXT,  -- Optional, for agent-specific memory
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(session_id, agent_id, key)
);

-- Archival memory (long-term with embeddings)
CREATE TABLE archival_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    agent_id TEXT,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding vector(4096),  -- pgvector column, padded to 4096 (Letta pattern)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Session entries (for branching - from v3 plan)
CREATE TABLE session_entries (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('session', 'message', 'branch', 'model_change')),
    parent_id TEXT REFERENCES session_entries(id),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    role TEXT,
    content TEXT,
    usage JSONB,
    branch_name TEXT,
    branch_description TEXT
);

-- Branches table
CREATE TABLE branches (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    parent_branch_id TEXT REFERENCES branches(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN DEFAULT FALSE
);

-- Indexes for efficient queries
CREATE INDEX idx_core_memory_session ON core_memory(session_id);
CREATE INDEX idx_core_memory_agent ON core_memory(session_id, agent_id);
CREATE INDEX idx_archival_session ON archival_memory(session_id);
CREATE INDEX idx_archival_agent ON archival_memory(session_id, agent_id);
CREATE INDEX idx_archival_created ON archival_memory(created_at DESC);
CREATE INDEX idx_session_entries_session ON session_entries(session_id);
CREATE INDEX idx_session_entries_parent ON session_entries(parent_id);
CREATE INDEX idx_branches_session ON branches(session_id);

-- Vector index for similarity search (using IVFFlat)
-- Note: Create after initial data load for better index quality
-- CREATE INDEX idx_archival_embedding ON archival_memory USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Full-text search index on content
CREATE INDEX idx_archival_content_fts ON archival_memory USING gin(to_tsvector('english', content));

-- Memory tags for organization and filtering (Phase 3.4)
CREATE TABLE memory_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID NOT NULL REFERENCES archival_memory(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    session_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(memory_id, tag)
);

CREATE INDEX idx_memory_tags_session ON memory_tags(session_id);
CREATE INDEX idx_memory_tags_tag ON memory_tags(tag);
CREATE INDEX idx_memory_tags_memory ON memory_tags(memory_id);
CREATE INDEX idx_memory_tags_session_tag ON memory_tags(session_id, tag);

-- ============================================================================
-- Temporal Memory Schema (Phase 3.1)
-- ============================================================================
-- Unified schema supporting both TemporalWriter (backfill) and
-- TemporalMemoryStore (session-scoped) implementations.
--
-- Key design decisions:
-- - UUID primary keys for distributed compatibility
-- - Superset of columns from both implementations
-- - Deferrable unique constraints for batch operations
-- - pgvector column for future semantic search
-- ============================================================================

-- Unified temporal_facts table (superset of both implementations)
CREATE TABLE IF NOT EXISTS temporal_facts (
    -- Primary key: UUID for PG compatibility
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core fields (both implementations)
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,

    -- Turn tracking (TemporalWriter uses 'turn', Store uses established/changed)
    turn INTEGER,                          -- TemporalWriter: single turn
    turn_established INTEGER,              -- TemporalMemoryStore: when first set
    turn_last_changed INTEGER,             -- TemporalMemoryStore: last modification

    -- Change tracking (TemporalMemoryStore only)
    change_count INTEGER DEFAULT 0,

    -- Deduplication (TemporalWriter)
    content_hash TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Vector embedding (Phase 3.6) - padded to 4096 (Letta pattern)
    embedding vector(4096),

    -- Constraints
    -- content_hash deduplication for TemporalWriter (backfill)
    CONSTRAINT uq_temporal_facts_hash UNIQUE (content_hash)

    -- NOTE: The (session_id, key) constraint was removed to allow TemporalWriter
    -- to store multiple facts with the same key (e.g., multiple file reads).
    -- TemporalMemoryStore should use DELETE + INSERT pattern for upserts instead.
    -- Original plan had: CONSTRAINT uq_temporal_facts_session_key UNIQUE (session_id, key)
);

-- Unified temporal_traces table (renamed from 'trace' to 'traces' for consistency)
CREATE TABLE IF NOT EXISTS temporal_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    turn INTEGER NOT NULL,

    -- TemporalWriter fields
    fact_count INTEGER DEFAULT 0,
    confidence REAL DEFAULT 1.0,

    -- TemporalMemoryStore fields
    facts_json JSONB,                      -- Snapshot of facts at turn
    erotetic_json JSONB,                   -- E(X,Q) evocation data

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Performance indexes for temporal_facts
CREATE INDEX IF NOT EXISTS idx_temporal_facts_session ON temporal_facts(session_id);
CREATE INDEX IF NOT EXISTS idx_temporal_facts_session_key ON temporal_facts(session_id, key);
CREATE INDEX IF NOT EXISTS idx_temporal_facts_turn ON temporal_facts(session_id, turn);
CREATE INDEX IF NOT EXISTS idx_temporal_facts_turn_established ON temporal_facts(session_id, turn_established);
CREATE INDEX IF NOT EXISTS idx_temporal_facts_hash ON temporal_facts(content_hash) WHERE content_hash IS NOT NULL;

-- Performance indexes for temporal_traces
CREATE INDEX IF NOT EXISTS idx_temporal_traces_session ON temporal_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_temporal_traces_turn ON temporal_traces(session_id, turn);

-- Full-text search on fact values
CREATE INDEX IF NOT EXISTS idx_temporal_facts_value_fts ON temporal_facts
    USING gin(to_tsvector('english', value));

-- Vector similarity index (create after initial data load for better index quality)
-- CREATE INDEX idx_temporal_facts_embedding ON temporal_facts
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- Permissions
-- ============================================================================

-- Grant minimal required permissions (principle of least privilege)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO agentica;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agentica;
