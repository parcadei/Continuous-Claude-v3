# 13. MCP Offline Mode

> **Architecture Reference**: See [00-architecture-decisions.md](./00-architecture-decisions.md) for authoritative decisions (113+ decisions from Round 3 interviews).

## Offline Capability

**MCP tools should degrade gracefully when offline.**

### Why Offline Matters

- Airplane coding
- Unstable internet connections
- Rate-limited APIs (fallback to local)
- Privacy-conscious environments
- Disaster recovery

### Progressive Degradation Pattern

**Check connectivity before calling remote APIs:**

```typescript
async function checkConnectivity(url: string): Promise<boolean> {
  try {
    const response = await fetch(url, {
      method: 'HEAD',
      signal: AbortSignal.timeout(2000)
    });
    return response.ok;
  } catch {
    return false;
  }
}

// Usage in MCP tool
async function search(query: string): Promise<SearchResult> {
  if (await checkConnectivity('https://api.example.com')) {
    // Use remote API
    return await remoteSearch(query);
  } else {
    // Fallback to local index
    console.warn('Offline: using local search index');
    return await localSearch(query);
  }
}
```

### Caching Strategy

**Cache remote responses for offline replay:**

```typescript
interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;  // Time to live in seconds
}

class OfflineCache<T> {
  private cache = new Map<string, CacheEntry<T>>();

  async get(key: string, fetcher: () => Promise<T>, ttl: number = 3600): Promise<T> {
    const cached = this.cache.get(key);

    // Return cached if fresh
    if (cached && Date.now() - cached.timestamp < cached.ttl * 1000) {
      console.log(`Cache hit: ${key}`);
      return cached.data;
    }

    // Fetch fresh data
    try {
      const data = await fetcher();
      this.cache.set(key, { data, timestamp: Date.now(), ttl });
      return data;
    } catch (error) {
      // If fetch fails, return stale cache (if exists)
      if (cached) {
        console.warn(`Offline: returning stale cache for ${key}`);
        return cached.data;
      }
      throw error;
    }
  }

  persist(path: string) {
    const entries = Array.from(this.cache.entries());
    fs.writeFileSync(path, JSON.stringify(entries));
  }

  load(path: string) {
    if (fs.existsSync(path)) {
      const entries = JSON.parse(fs.readFileSync(path, 'utf-8'));
      this.cache = new Map(entries);
    }
  }
}

// Usage
const cache = new OfflineCache<SearchResult>();
cache.load('.claude/cache/search.json');

const result = await cache.get('query:' + query, () => remoteSearch(query), 3600);

// Persist on exit
process.on('exit', () => cache.persist('.claude/cache/search.json'));
```

### Local Alternatives

**Prefer tools with local fallbacks:**

| Remote Tool | Local Fallback |
|-------------|----------------|
| Perplexity search | ripgrep + local docs |
| OpenAI embeddings | Local sentence-transformers |
| Cloud LLM (GPT-4) | Local LLM (Ollama) |
| GitHub API | Local git commands |
| Web scraping | Cached HTML files |

**Example: Search with fallback:**

```bash
# Try remote first
if curl -s --max-time 2 https://api.perplexity.ai/health > /dev/null; then
  # Use Perplexity
  uv run python scripts/perplexity_search.py --query "$QUERY"
else
  # Fallback to local grep
  echo "Offline: using local search"
  rg "$QUERY" --json | jq '.data.lines.text'
fi
```

### Configuration

**User controls online/offline mode:**

```json
// .claude/settings.json
{
  "offlineMode": "auto",  // auto | online | offline
  "cacheTTL": 3600,       // seconds
  "fallbackBehavior": "warn"  // warn | silent | error
}
```

**Modes:**
- `auto`: Detect connectivity and fallback automatically
- `online`: Fail if remote unavailable (no fallback)
- `offline`: Never call remote APIs (always use cache/local)

### Offline-First Tools

**Design MCP tools to work offline by default:**

**Bad (requires network):**
```python
def search_codebase(query: str) -> List[Match]:
    # Always calls remote API
    return requests.post('https://api.example.com/search', json={'query': query})
```

**Good (offline-first):**
```python
def search_codebase(query: str) -> List[Match]:
    # 1. Try local index first
    local_results = search_local_index(query)
    if local_results:
        return local_results

    # 2. If online, enhance with remote
    if is_online():
        remote_results = search_remote_api(query)
        # Merge and cache for next time
        update_local_index(remote_results)
        return merge_results(local_results, remote_results)

    # 3. Return local results even if empty
    return local_results
```

### Cache Priming

**Pre-populate cache for known queries:**

```bash
# Before going offline (e.g., at airport)
npm run cache:prime

# Script pre-fetches common queries
# - Recent codebase searches
# - Frequently accessed docs
# - LLM responses for common patterns
```

**Automatic priming:**
```bash
# SessionEnd hook: cache popular queries
cat > .claude/hooks/session-end-cache-prime.sh <<'EOF'
#!/bin/bash
set -e

# Extract queries from session
QUERIES=$(cat "$CLAUDE_SESSION_LOG" | jq -r '.tool_calls[] | select(.tool == "morph__search") | .arguments.query' | sort | uniq)

# Pre-fetch each query
while IFS= read -r query; do
  echo "Caching query: $query"
  uv run python scripts/morph_search.py --query "$query" > /dev/null
done <<< "$QUERIES"
EOF
```

### Offline Testing

**Test tools in offline mode:**

```bash
# Disable network (macOS)
sudo ifconfig en0 down

# Run tool
uv run python scripts/search.py --query "authentication"

# Verify fallback works
echo "✅ Offline mode works" || echo "❌ Requires network"

# Re-enable network
sudo ifconfig en0 up
```

**CI/CD offline tests:**
```yaml
# .github/workflows/offline-tests.yml
name: Offline Mode Tests
on: [push]

jobs:
  offline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Disable network
        run: sudo iptables -A OUTPUT -j DROP

      - name: Run offline tests
        run: npm run test:offline

      - name: Re-enable network
        run: sudo iptables -F
```

### Isolation Setup for Offline Mode

**Claude Code isolation supports offline workflows:**

When working offline, you can use `CLAUDE_CONFIG_DIR` to point to a local-only configuration:

```bash
# Setup offline-specific config
export CLAUDE_CONFIG_DIR="$HOME/.config/claude-offline"
mkdir -p "$CLAUDE_CONFIG_DIR"

# Offline settings.json (no remote MCP servers)
cat > "$CLAUDE_CONFIG_DIR/settings.json" <<'EOF'
{
  "mcpServers": {
    "local-search": {
      "command": "rg",
      "args": ["--json"]
    },
    "local-llm": {
      "command": "ollama",
      "args": ["serve"]
    }
  },
  "offlineMode": "offline"
}
EOF

# Use offline config
claude --project /path/to/project
```

See [15-security.md](./15-security.md) for more on Claude Code isolation setup.

### Metrics

**Track offline vs online usage:**

```typescript
interface OfflineMetrics {
  totalCalls: number;
  onlineCalls: number;
  offlineCalls: number;
  cacheHits: number;
  cacheMisses: number;
}

// Log to .claude/cache/offline-metrics.json
function recordCall(online: boolean, cacheHit: boolean) {
  const metrics: OfflineMetrics = loadMetrics();
  metrics.totalCalls++;
  if (online) {
    metrics.onlineCalls++;
  } else {
    metrics.offlineCalls++;
  }
  if (cacheHit) {
    metrics.cacheHits++;
  } else {
    metrics.cacheMisses++;
  }
  saveMetrics(metrics);
}

// Report
function reportMetrics() {
  const metrics = loadMetrics();
  const offlineRate = (metrics.offlineCalls / metrics.totalCalls) * 100;
  const cacheHitRate = (metrics.cacheHits / metrics.totalCalls) * 100;

  console.log(`Offline rate: ${offlineRate.toFixed(1)}%`);
  console.log(`Cache hit rate: ${cacheHitRate.toFixed(1)}%`);
}
```

### User Notifications

**Inform user when falling back to offline:**

```typescript
function notifyOffline(toolName: string, fallback: string) {
  console.warn(`
⚠️  Offline Mode Detected

Tool: ${toolName}
Fallback: ${fallback}

Note: Results may be stale or incomplete.
Connect to internet for latest data.
  `.trim());
}

// Usage
if (!await checkConnectivity(apiUrl)) {
  notifyOffline('perplexity-search', 'local ripgrep');
  return await localSearch(query);
}
```

### Documentation

**Update skill docs with offline behavior:**

```markdown
## Offline Support

This skill works offline with reduced functionality:

- **Online**: Uses Perplexity API for web-enhanced search
- **Offline**: Falls back to local ripgrep search
- **Cache**: Previously searched queries available offline (TTL: 1 hour)

To pre-populate cache:
\`\`\`bash
npm run cache:prime
\`\`\`
```

---

## Summary

- All remote MCP tools should have local fallbacks
- Cache responses for offline replay (TTL configurable)
- Progressive degradation pattern (try remote → fallback to local)
- User controls offline mode (`auto`, `online`, `offline`)
- Offline testing in CI/CD
- Claude Code isolation (CLAUDE_CONFIG_DIR) supports offline configs
- Metrics track online vs offline usage
- Clear user notifications when offline
