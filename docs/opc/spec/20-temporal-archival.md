# Module: Temporal Archival Strategy

## Overview

Indefinite retention in PostgreSQL with tiered storage. Facts older than 90 days archived to cold storage with LLM summarization.

---

## Storage Tiers

| Tier | Storage | Age | Access |
|------|---------|-----|--------|
| Hot | PostgreSQL | 0-90 days | Full query, vector search |
| Cold | Disk (gzipped JSONL) | >90 days | Manual restore |

---

## Archival Strategy by Fact Type

| Fact Type | Archival Action |
|-----------|-----------------|
| **Invariants (G())** | Keep forever (already minimal, high value) |
| **High-utility transitions** | Archive as-is |
| **Low-utility HOLDS** | Prune (transition history captures changes) |
| **Embeddings** | Drop (re-compute if needed) |

---

## Archival Pipeline

```python
async def archive_old_facts(cutoff_days: int = 90):
    """Archive facts older than cutoff to cold storage."""

    cutoff = datetime.now() - timedelta(days=cutoff_days)

    # Get old facts
    old_facts = await pool.fetch("""
        SELECT * FROM temporal_facts
        WHERE created_at < $1
        ORDER BY session_id, turn
    """, cutoff)

    # Group by session
    by_session = defaultdict(list)
    for fact in old_facts:
        by_session[fact["session_id"]].append(fact)

    for session_id, facts in by_session.items():
        # Generate LLM summary
        summary = await generate_session_summary(facts)

        # Write raw archive
        archive_path = Path(f"archive/temporal/{session_id}.jsonl.gz")
        archive_path.parent.mkdir(parents=True, exist_ok=True)

        with gzip.open(archive_path, 'wt') as f:
            for fact in facts:
                f.write(json.dumps(fact) + '\n')

        # Store summary in hot storage
        await pool.execute("""
            INSERT INTO temporal_summaries (session_id, summary, archived_at)
            VALUES ($1, $2, NOW())
        """, session_id, summary)

        # Delete from hot storage (keep invariants)
        await pool.execute("""
            DELETE FROM temporal_facts
            WHERE session_id = $1
            AND created_at < $2
            AND operator != 'G'  -- Keep invariants
        """, session_id, cutoff)

async def generate_session_summary(facts: list[dict]) -> str:
    """Generate LLM summary of session facts."""

    # Extract key information
    invariants = [f for f in facts if f["operator"] == "G"]
    transitions = [f for f in facts if f["operator"] == "holds"]

    prompt = f"""
Summarize this session's temporal facts into a concise digest:

Invariants (facts that never changed):
{json.dumps(invariants, indent=2)}

Transitions (state changes):
{json.dumps(transitions[-20:], indent=2)}  # Last 20

Return a 2-3 paragraph summary of:
1. What was the session about?
2. Key decisions made
3. Final outcomes
"""

    response = await claude_api.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text
```

---

## Restore from Archive

```python
async def restore_session_facts(session_id: str):
    """Restore archived facts to hot storage."""

    archive_path = Path(f"archive/temporal/{session_id}.jsonl.gz")

    if not archive_path.exists():
        raise FileNotFoundError(f"No archive for session {session_id}")

    with gzip.open(archive_path, 'rt') as f:
        for line in f:
            fact = json.loads(line)

            # Re-insert to hot storage
            await pool.execute("""
                INSERT INTO temporal_facts (...)
                VALUES (...)
                ON CONFLICT DO NOTHING
            """, ...)

    # Re-compute embeddings if needed
    await recompute_embeddings(session_id)
```

---

## Schema Additions

```sql
CREATE TABLE temporal_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fact_count INTEGER,
    date_range TSTZRANGE
);

CREATE INDEX idx_summaries_session ON temporal_summaries(session_id);
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/temporal_memory/archiver.py` | Archival pipeline |
| `scripts/temporal_memory/restore.py` | Restore from cold storage |
| `scripts/temporal_memory/summarizer_llm.py` | LLM summary generation |
