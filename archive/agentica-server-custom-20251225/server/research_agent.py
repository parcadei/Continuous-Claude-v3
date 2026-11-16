"""Research Agent - Queries Perplexity and Nia for research tasks.

This agent provides:
- Web search via Perplexity (multiple modes: quick, research, reasoning, deep)
- Documentation search via Nia (universal, package, web)
- State persistence of findings, sources, and query history
- Follow-up queries that reference prior findings

Usage via server:
    POST /agent/research/query
    {"query": "What are best practices for MCP server implementation?"}
"""

import asyncio
from typing import Any, Callable, Coroutine

from .registry import register_agent

# Import underlying search functions
from scripts.perplexity_search import (
    chat_query as perplexity_chat,
    search_query as perplexity_search_fn,
)
from scripts.nia_docs import (
    search_universal as search_universal_fn,
    search_web as search_web_fn,
    search_deep as search_deep_fn,
    oracle_research as oracle_research_fn,
)


RESEARCH_PREMISE = """You are a Research Agent with access to multiple search tools.

Your capabilities:
1. **Perplexity Search** - Web search with AI synthesis
   - perplexity_search(query): Direct web search with ranked results
   - perplexity_research(query): AI-synthesized research (sonar-pro)
   - perplexity_reason(query): Chain-of-thought reasoning
   - perplexity_deep(query): Comprehensive deep research

2. **Nia Documentation** - Technical documentation and code search
   - nia_search(query): Universal search across indexed sources
   - nia_web(query): Web search via Nia
   - nia_oracle(query): Autonomous research agent (Pro)

Your task:
- Answer research questions by combining multiple sources
- Track findings in your state for follow-up queries
- Cite sources in your responses
- Reference prior findings when relevant

State you maintain:
- findings: List of key discoveries
- sources: Dict mapping URLs to titles/snippets
- query_history: List of queries processed
- current_topic: The current research focus

When answering:
1. First check if you have relevant prior findings
2. Use appropriate search tools based on the query type
3. Synthesize results into a coherent answer
4. Update your state with new findings
"""


def _sync_to_async(fn: Callable[..., Any]) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Convert a sync function to async."""
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(fn, *args, **kwargs)
    return wrapper


def get_research_scope() -> dict[str, Callable[..., Coroutine[Any, Any, Any]]]:
    """Get research scope functions for the agent.

    Returns:
        Dict of async functions for Perplexity and Nia searches
    """
    # Wrap sync functions as async using to_thread for CPU-bound work
    async def perplexity_search(query: str, max_results: int = 10) -> dict:
        """Search web via Perplexity (direct results, no AI synthesis)."""
        return await asyncio.to_thread(
            perplexity_search_fn, query, max_results
        )

    async def perplexity_research(query: str) -> dict:
        """AI-synthesized research via Perplexity (sonar-pro)."""
        return await asyncio.to_thread(
            perplexity_chat, query, "sonar-pro"
        )

    async def perplexity_reason(query: str) -> dict:
        """Chain-of-thought reasoning via Perplexity (sonar-reasoning-pro)."""
        return await asyncio.to_thread(
            perplexity_chat, query, "sonar-reasoning-pro"
        )

    async def perplexity_deep(query: str) -> dict:
        """Deep comprehensive research via Perplexity (sonar-deep-research)."""
        return await asyncio.to_thread(
            perplexity_chat, query, "sonar-deep-research"
        )

    # Nia functions are already async
    async def nia_search(query: str, limit: int = 10) -> dict:
        """Universal search across Nia indexed sources."""
        return await search_universal_fn(query, limit)

    async def nia_web(query: str) -> dict:
        """Web search via Nia."""
        return await search_web_fn(query)

    async def nia_deep(query: str) -> dict:
        """Deep research via Nia."""
        return await search_deep_fn(query)

    async def nia_oracle(query: str) -> dict:
        """Autonomous research via Nia Oracle (Pro only)."""
        return await oracle_research_fn(query)

    return {
        "perplexity_search": perplexity_search,
        "perplexity_research": perplexity_research,
        "perplexity_reason": perplexity_reason,
        "perplexity_deep": perplexity_deep,
        "nia_search": nia_search,
        "nia_web": nia_web,
        "nia_deep": nia_deep,
        "nia_oracle": nia_oracle,
    }


class StatefulAgent:
    """Wrapper that adds state management to Agentica agents.

    Agentica agents don't have built-in state - conversation history
    lives in Symbolica's backend. This wrapper provides our own
    state dict that we can persist to disk.
    """

    def __init__(self, agent, initial_state: dict | None = None):
        self._agent = agent
        self.state = initial_state or {}

    async def call(self, return_type, task: str, **scope):
        """Delegate to underlying agent."""
        return await self._agent.call(return_type, task, **scope)

    def total_usage(self):
        """Get total token usage."""
        return self._agent.total_usage()

    def last_usage(self):
        """Get last invocation usage."""
        return self._agent.last_usage()


@register_agent("research")
async def create_research_agent():
    """Create a Research agent with Perplexity and Nia scope.

    Returns:
        StatefulAgent wrapping Agentica agent with our state dict
    """
    from agentica import spawn

    scope = get_research_scope()

    agent = await spawn(
        premise=RESEARCH_PREMISE,
        scope=scope,
    )

    # Wrap with our state management
    stateful = StatefulAgent(agent, initial_state={
        "findings": [],
        "sources": {},
        "query_history": [],
        "current_topic": None,
    })

    return stateful
