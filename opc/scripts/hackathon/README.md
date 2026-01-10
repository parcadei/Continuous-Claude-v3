# CCv3 Hackathon - Minimal Viable Integration

**Focus:** Simplest working implementation that showcases sponsors.

## Quick Start

```bash
# 1. Set environment variables
export MONGODB_URI="mongodb+srv://..."
export FIREWORKS_API_KEY="fw_..."
export JINA_API_KEY="jina_..."

# 2. Run tests
python -m scripts.hackathon.test_integrations

# 3. Run demo
python -m scripts.hackathon.demo
```

## Files

| File | Purpose |
|------|---------|
| `mongo_client.py` | Simple MongoDB Atlas client with hybrid search |
| `embeddings.py` | Jina v3 embeddings (fallback to local) |
| `inference.py` | Fireworks AI LLM calls |
| `eval_gate.py` | Galileo-style quality gate |
| `demo.py` | End-to-end demo script |
| `test_integrations.py` | Verify all integrations work |

## What Judges See

1. **MongoDB Atlas**: Hybrid search with RRF (text + vector combined)
2. **Fireworks AI**: Fast LLM inference with function calling
3. **Jina v3**: Task-specific embeddings for retrieval
4. **Galileo**: Quality gate before commits
