# Ragie RAG

Query decision theory and modal logic knowledge base via Ragie.

## Partitions

| Partition | Books |
|-----------|-------|
| `decision-theory` | Sutton & Barto RL, LaValle Planning Algorithms |
| `modal-logic` | Blackburn Modal Logic, Huth Logic in CS |

## Query

```bash
# Decision theory queries
uv run python scripts/ragie_query.py -q "Bellman equation" -p decision-theory

# Modal logic queries
uv run python scripts/ragie_query.py -q "Kripke semantics" -p modal-logic

# Cross-partition search
uv run python scripts/ragie_query.py -q "your query"

# More results + rerank
uv run python scripts/ragie_query.py -q "MDP value iteration" -p decision-theory -k 10 --rerank
```

## Upload New Books

```bash
# Single file
uv run python scripts/ragie_upload.py --file ~/path/to/book.pdf --partition decision-theory

# Directory
uv run python scripts/ragie_upload.py --dir ~/books/ --partition modal-logic
```

## Check Status

```bash
# List all in partition
uv run python scripts/ragie_status.py --list --partition decision-theory

# Check specific doc
uv run python scripts/ragie_status.py --doc-id <id>
```

## Options

| Option | Description |
|--------|-------------|
| `-q, --query` | Search query |
| `-p, --partition` | Filter by partition |
| `-k, --top-k` | Number of results (default: 5) |
| `--rerank` | Enable reranking for better relevance |
| `--json` | Output raw JSON |

Requires `RAGIE_API_KEY` in `~/.claude/.env`.
