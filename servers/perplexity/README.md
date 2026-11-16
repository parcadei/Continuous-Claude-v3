# perplexity MCP Tools

Auto-generated wrappers for perplexity MCP server.

## Tools

- `perplexity_ask`: Engages in a conversation using the Sonar API. Accepts an array of messages (each with a role and content) and returns a chat completion response from the Perplexity model.
- `perplexity_research`: Performs deep research using the Perplexity API. Accepts an array of messages (each with a role and content) and returns a comprehensive research response with citations.
- `perplexity_reason`: Performs reasoning tasks using the Perplexity API. Accepts an array of messages (each with a role and content) and returns a well-reasoned response using the sonar-reasoning-pro model.
- `perplexity_search`: Performs web search using the Perplexity Search API. Returns ranked search results with titles, URLs, snippets, and metadata. Perfect for finding up-to-date facts, news, or specific information.

## Usage

```python
from servers.perplexity import perplexity_ask

# Use the tool
result = await perplexity_ask(params)
```

**Note**: This file is auto-generated. Do not edit manually.
