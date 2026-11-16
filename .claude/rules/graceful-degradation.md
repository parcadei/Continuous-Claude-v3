# Graceful Degradation with Helpful Messages

When optional services are unavailable, degrade gracefully with actionable fallback messages.

## Pattern

Check availability at the start, cache the result, and provide helpful messages that explain what's missing and how to fix it.

## DO

- Check service availability early (before wasting compute)
- Cache health check results for the session (e.g., 60s TTL)
- Provide actionable fallback messages:
  - What service is missing
  - What features are degraded
  - How to enable the service
- Continue with reduced functionality when possible

## DON'T

- Silently fail or return empty results
- Check availability on every call (cache it)
- Assume the user knows how to start missing services

## Example: LMStudio Check Pattern

```typescript
let lmstudioAvailable: boolean | null = null;
let lastCheck = 0;
const CACHE_TTL = 60000; // 60 seconds

async function checkLMStudio(): Promise<boolean> {
  const now = Date.now();
  if (lmstudioAvailable !== null && now - lastCheck < CACHE_TTL) {
    return lmstudioAvailable;
  }

  try {
    const response = await fetch('http://localhost:1234/v1/models', {
      signal: AbortSignal.timeout(2000)
    });
    lmstudioAvailable = response.ok;
  } catch {
    lmstudioAvailable = false;
  }
  lastCheck = now;
  return lmstudioAvailable;
}

// Usage
if (!await checkLMStudio()) {
  return {
    result: 'continue',
    message: `LMStudio not available at localhost:1234.

To enable Godel-Prover tactic suggestions:
1. Install LMStudio from https://lmstudio.ai/
2. Load "Goedel-Prover-V2-8B" model
3. Start the local server on port 1234

Continuing without AI-assisted tactics...`
  };
}
```

## Fallback Message Template

```
[Service] not available at [endpoint].

To enable [feature]:
1. [Step to install/start]
2. [Configuration step if needed]
3. [Verification step]

Continuing without [degraded feature]...
```

## Source Sessions

- This session: LMStudio availability check with 60s caching and helpful fallback
- 174e0ff3: Environment variable debugging - print computed paths for troubleshooting
