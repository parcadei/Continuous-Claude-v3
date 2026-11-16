"""Mutation testing + bug research agent for reranker hardening.

This agent analyzes code for mutation testing gaps and researches common bugs
using Nia documentation search.
"""

import json
import subprocess
from pathlib import Path

from agentica import spawn


async def nia_search(query: str, limit: int = 5) -> dict:
    """Search library documentation via Nia universal search."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "runtime.harness",
            "scripts/nia_docs.py",
            "search",
            "universal",
            query,
            "--limit",
            str(limit),
        ],
        capture_output=True,
        text=True,
        cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit",
    )
    if result.stdout:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw_output": result.stdout}
    return {"error": result.stderr}


async def read_file(path: str) -> str:
    """Read a file from disk."""
    return Path(path).read_text()


async def analyze_reranker_mutations():
    """Analyze reranker.py for mutation testing gaps and research common bugs."""

    # Spawn research agent
    researcher = await spawn(
        premise="""You are a mutation testing and bug research expert.

Your task:
1. Analyze Python code for mutation testing gaps (what mutations tests wouldn't catch)
2. Research common bugs in the same domain using Nia docs
3. Synthesize findings into actionable test recommendations

Focus on:
- Boundary conditions (edge cases in parameters like top_k)
- Error handling (API failures, network timeouts, malformed responses)
- Type coercion (score as int vs float, None handling)
- Empty/None input handling
- Async patterns (httpx client lifecycle, executor cleanup)
- Cross-encoder model edge cases
""",
        scope={
            "nia_search": nia_search,
            "read_file": read_file,
        },
        model="anthropic:claude-sonnet-4.5",
    )

    # Run analysis
    result = await researcher.call(
        dict,
        """Analyze scripts/agentica/reranker.py for mutation testing gaps and research common bugs.

Steps:
1. Read the reranker.py file
2. Identify mutations that existing tests would NOT catch:
   - Boundary conditions (top_k=0, top_k > len(documents), top_k=None)
   - Error handling (what if API returns 500? timeout? malformed JSON?)
   - Type safety (score coercion, None handling)
   - Empty inputs (empty documents list, empty query string)
   - Resource cleanup (executor, httpx client)

3. Research common bugs using nia_search:
   - "cross-encoder reranking bugs edge cases"
   - "httpx async client lifecycle bugs"
   - "sentence-transformers thread pool issues"
   - "cohere rerank API error handling"

4. Return structured analysis:
{
  "surviving_mutations": [
    {"mutation": "...", "would_catch": false, "reason": "...", "priority": "high|medium|low"}
  ],
  "bug_categories": [
    {"category": "...", "risk": "high|medium|low", "examples": [...]}
  ],
  "recommended_tests": [
    {"test": "...", "priority": "high|medium|low", "rationale": "..."}
  ]
}
""",
        code_path="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/reranker.py",
    )

    return result


async def main():
    """Run mutation and bug analysis."""
    print("Starting mutation + bug research for reranker...")
    analysis = await analyze_reranker_mutations()

    # Format output
    output = f"""# Mutation + Bug Analysis

## Surviving Mutations (Gaps)

| Mutation | Would Catch? | Reason | Priority |
|----------|--------------|--------|----------|
"""

    for mutation in analysis.get("surviving_mutations", []):
        output += f"| {mutation['mutation']} | {'✓' if mutation['would_catch'] else '✗'} | {mutation['reason']} | {mutation['priority']} |\n"

    output += "\n## Bug Categories Found\n\n"
    for category in analysis.get("bug_categories", []):
        output += f"**{category['category']}** (Risk: {category['risk']})\n"
        for example in category.get("examples", []):
            output += f"- {example}\n"
        output += "\n"

    output += "## Recommended Tests\n\n"
    for test in analysis.get("recommended_tests", []):
        output += f"**{test['priority'].upper()}**: {test['test']}\n"
        output += f"- Rationale: {test['rationale']}\n\n"

    # Write to output file
    output_path = Path(
        "/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/thoughts/shared/work/reranker-pipeline/phase2-hardening/01-mutation-bugs.md"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output)

    print(f"\n✓ Analysis written to: {output_path}")
    print(f"\nFound {len(analysis.get('surviving_mutations', []))} mutation gaps")
    print(f"Found {len(analysis.get('bug_categories', []))} bug categories")
    print(f"Recommended {len(analysis.get('recommended_tests', []))} tests")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
