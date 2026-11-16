-- Migration: Add memory_tags table for tag-based filtering (Phase 3.4)
--
-- Purpose:
--   Enable tag-based organization and filtering of archival memories.
--   Supports "any" (OR) and "all" (AND) matching modes for flexible queries.
--
-- Tables created:
--   - memory_tags: Maps memory IDs to tags with session isolation
--
-- Run with:
--   psql $AGENTICA_POSTGRES_URL -f scripts/migrations/003_add_memory_tags.sql

BEGIN;

-- ============================================================================
-- memory_tags table
-- ============================================================================

CREATE TABLE IF NOT EXISTS memory_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID NOT NULL REFERENCES archival_memory(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    session_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    -- Ensure each memory-tag combination is unique
    UNIQUE(memory_id, tag)
);

-- Index for finding all tags in a session (for get_all_session_tags)
CREATE INDEX IF NOT EXISTS idx_memory_tags_session ON memory_tags(session_id);

-- Index for finding memories by tag (for search_with_tags)
CREATE INDEX IF NOT EXISTS idx_memory_tags_tag ON memory_tags(tag);

-- Index for finding tags by memory (for get_tags)
CREATE INDEX IF NOT EXISTS idx_memory_tags_memory ON memory_tags(memory_id);

-- Composite index for session + tag queries (most common filter pattern)
CREATE INDEX IF NOT EXISTS idx_memory_tags_session_tag ON memory_tags(session_id, tag);

COMMIT;

-- Verification queries (run manually to confirm migration)
-- SELECT
--     table_name,
--     column_name,
--     data_type,
--     is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'memory_tags'
-- ORDER BY ordinal_position;
--
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'memory_tags';
