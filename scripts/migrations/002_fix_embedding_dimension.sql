-- Migration: Fix embedding dimension from 1024 to 4096
-- Required for Letta pattern compatibility (memory_service_pg.py pads to 4096)
--
-- Background:
--   The memory_service_pg.py _pad_embedding() method pads all embeddings
--   to 4096 dimensions before storage. This allows storing embeddings from
--   any provider (Voyage=1024, OpenAI=1536, etc.) in a unified format.
--
-- Tables affected:
--   - archival_memory.embedding
--   - temporal_facts.embedding
--
-- Run with:
--   psql $AGENTICA_POSTGRES_URL -f scripts/migrations/002_fix_embedding_dimension.sql

BEGIN;

-- ============================================================================
-- archival_memory table
-- ============================================================================

-- Drop existing vector index if exists (required before ALTER COLUMN)
DROP INDEX IF EXISTS idx_archival_embedding;
DROP INDEX IF EXISTS idx_archival_memory_embedding;

-- Alter column dimension from 1024 to 4096
-- Note: This will fail if there is existing data with 1024-dim vectors
-- In that case, you'll need to re-embed or pad existing data first
ALTER TABLE archival_memory
ALTER COLUMN embedding TYPE vector(4096);

-- Recreate index with updated dimension
-- Using IVFFlat for approximate nearest neighbor search
-- lists = 100 is a reasonable default for moderate-sized datasets
CREATE INDEX idx_archival_memory_embedding ON archival_memory
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- temporal_facts table
-- ============================================================================

-- Drop existing vector index if exists
DROP INDEX IF EXISTS idx_temporal_facts_embedding;

-- Alter column dimension from 1024 to 4096
ALTER TABLE temporal_facts
ALTER COLUMN embedding TYPE vector(4096);

-- Recreate index (optional - uncomment if vector search is heavily used)
-- CREATE INDEX idx_temporal_facts_embedding ON temporal_facts
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

COMMIT;

-- Verification queries (run manually to confirm migration)
-- SELECT
--     column_name,
--     udt_name,
--     character_maximum_length
-- FROM information_schema.columns
-- WHERE table_name IN ('archival_memory', 'temporal_facts')
-- AND column_name = 'embedding';
