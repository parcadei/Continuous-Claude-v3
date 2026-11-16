#!/usr/bin/env python3
"""Perplexity AI Search - Web search, research, and reasoning via Perplexity API.

Use Cases:
- Direct web search with ranked results
- AI-powered research with synthesis
- Chain-of-thought reasoning
- Deep comprehensive research

Models (2025):
- sonar: Lightweight search with grounding
- sonar-pro: Advanced search for complex queries
- sonar-reasoning-pro: Precise reasoning with Chain of Thought
- sonar-deep-research: Expert-level exhaustive research

Usage:
  # Quick question (AI answer)
  uv run python scripts/perplexity_search.py --ask "What is the latest version of Python?"

  # Direct web search (ranked results, no AI synthesis)
  uv run python scripts/perplexity_search.py --search "SQLite graph database patterns"

  # AI-synthesized research (sonar-pro)
  uv run python scripts/perplexity_search.py --research "compare FastAPI vs Django for microservices"

  # Chain-of-thought reasoning (sonar-reasoning-pro)
  uv run python scripts/perplexity_search.py --reason "should I use MongoDB or PostgreSQL for a chat app?"

  # Deep comprehensive research (sonar-deep-research)
  uv run python scripts/perplexity_search.py --deep "state of AI agent observability 2025"

Requires: PERPLEXITY_API_KEY in environment or ~/.claude/.env
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


# API configuration
CHAT_URL = "https://api.perplexity.ai/chat/completions"
SEARCH_URL = "https://api.perplexity.ai/search"

# Available models (2025)
MODELS = {
    "sonar": "sonar",
    "sonar-pro": "sonar-pro",
    "sonar-reasoning-pro": "sonar-reasoning-pro",
    "sonar-deep-research": "sonar-deep-research",
}


def load_api_key() -> str:
    """Load API key from environment or ~/.claude/.env."""
    api_key = os.environ.get("PERPLEXITY_API_KEY", "")

    if not api_key:
        # Try loading from ~/.claude/.env
        env_file = Path.home() / ".claude" / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("PERPLEXITY_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

    return api_key


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="AI search via Perplexity API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Models:
  sonar              Lightweight search with grounding
  sonar-pro          Advanced search for complex queries
  sonar-reasoning-pro  Chain of thought reasoning
  sonar-deep-research  Expert-level comprehensive research

Examples:
  %(prog)s --ask "What is MCP?"
  %(prog)s --search "SQLite recursive CTE examples"
  %(prog)s --research "best practices for AI agent logging 2025"
  %(prog)s --reason "Neo4j vs SQLite for small graph under 10k nodes"
  %(prog)s --deep "comprehensive guide to OpenTelemetry for AI agents"
        """
    )

    # Modes (mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ask", metavar="QUERY",
                       help="Quick question with AI answer (sonar)")
    group.add_argument("--search", metavar="QUERY",
                       help="Direct web search - ranked results without AI synthesis")
    group.add_argument("--research", metavar="QUERY",
                       help="AI-synthesized research (sonar-pro)")
    group.add_argument("--reason", metavar="QUERY",
                       help="Chain-of-thought reasoning (sonar-reasoning-pro)")
    group.add_argument("--deep", metavar="QUERY",
                       help="Deep comprehensive research (sonar-deep-research)")

    # Search options (for --search mode)
    parser.add_argument("--max-results", type=int, default=10,
                        help="Max results for --search (1-20, default: 10)")
    parser.add_argument("--recency", choices=["day", "week", "month", "year"],
                        help="Filter by recency for --search")
    parser.add_argument("--domains", nargs="+",
                        help="Limit to specific domains for --search")

    # Optional model override
    parser.add_argument("--model", choices=list(MODELS.keys()),
                        help="Override model selection")

    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


async def chat_query(query: str, model: str = "sonar") -> dict:
    """Make request to /chat/completions endpoint (AI-synthesized answers)."""
    import aiohttp

    api_key = load_api_key()
    if not api_key:
        return {"error": "PERPLEXITY_API_KEY not found in environment or ~/.claude/.env"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": query}
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            CHAT_URL,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=120)  # Longer for deep research
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                return {"error": f"API error {response.status}: {error_text}"}

            result = await response.json()

            # Extract the response
            answer = ""
            citations = []

            if "choices" in result and result["choices"]:
                choice = result["choices"][0]
                if "message" in choice:
                    answer = choice["message"].get("content", "")

            # Extract citations if available
            if "citations" in result:
                citations = result["citations"]

            return {
                "answer": answer,
                "citations": citations,
                "model": result.get("model", model),
                "usage": result.get("usage", {})
            }


async def search_query(query: str, max_results: int = 10,
                       recency: str = None, domains: list = None) -> dict:
    """Make request to /search endpoint (direct ranked results)."""
    import aiohttp

    api_key = load_api_key()
    if not api_key:
        return {"error": "PERPLEXITY_API_KEY not found in environment or ~/.claude/.env"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "query": query,
        "max_results": max_results,
    }

    if recency:
        payload["search_recency_filter"] = recency
    if domains:
        payload["search_domain_filter"] = domains

    async with aiohttp.ClientSession() as session:
        async with session.post(
            SEARCH_URL,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                return {"error": f"API error {response.status}: {error_text}"}

            result = await response.json()

            return {
                "results": result.get("results", []),
                "id": result.get("id", "")
            }


async def main():
    args = parse_args()

    # Direct search mode (uses /search endpoint)
    if args.search:
        query = args.search
        print(f"Searching: {query}")
        if args.recency:
            print(f"  Recency: {args.recency}")
        if args.domains:
            print(f"  Domains: {', '.join(args.domains)}")

        result = await search_query(
            query,
            max_results=args.max_results,
            recency=args.recency,
            domains=args.domains
        )

        if "error" in result and result["error"]:
            print(f"\n❌ Error: {result['error']}")
            sys.exit(1)

        results = result.get("results", [])
        print(f"\n✓ Found {len(results)} results\n")

        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            url = r.get("url", "")
            snippet = r.get("snippet", "")[:200]
            date = r.get("date", "")

            print(f"**{i}. {title}**")
            print(f"   {url}")
            if date:
                print(f"   Date: {date}")
            if snippet:
                print(f"   {snippet}...")
            print()

        return

    # Chat/AI modes (use /chat/completions endpoint)
    if args.ask:
        query = args.ask
        model = args.model or "sonar"
        mode = "Ask"
        print(f"Asking ({model}): {query}")

    elif args.research:
        query = args.research
        model = args.model or "sonar-pro"
        mode = "Research"
        print(f"Researching ({model}): {query}")

    elif args.reason:
        query = args.reason
        model = args.model or "sonar-reasoning-pro"
        mode = "Reason"
        print(f"Reasoning ({model}): {query}")

    elif args.deep:
        query = args.deep
        model = args.model or "sonar-deep-research"
        mode = "Deep Research"
        print(f"Deep researching ({model}): {query}")
        print("  (This may take a minute...)")

    result = await chat_query(query, model)

    if "error" in result and result["error"]:
        print(f"\n❌ Error: {result['error']}")
        sys.exit(1)

    print(f"\n✓ {mode} complete (model: {result.get('model', model)})\n")

    # Print answer
    if result.get("answer"):
        print(result["answer"])

    # Print citations if available
    if result.get("citations"):
        print("\n📚 Sources:")
        for i, cite in enumerate(result["citations"][:10], 1):
            if isinstance(cite, dict):
                url = cite.get("url", cite.get("title", str(cite)))
                print(f"  {i}. {url}")
            else:
                print(f"  {i}. {cite}")

    # Print usage stats
    if result.get("usage"):
        usage = result["usage"]
        tokens = usage.get("total_tokens", 0)
        if tokens:
            print(f"\n📊 Tokens: {tokens}")


if __name__ == "__main__":
    asyncio.run(main())
