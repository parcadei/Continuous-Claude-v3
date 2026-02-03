"""
Tree Search - LLM-based reasoning for finding relevant nodes in tree indexes.

Uses hierarchical tree structure + LLM reasoning (98.7% accuracy)
instead of vector similarity (~50%).
"""
import json
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from .claude_llm import claude_complete, claude_complete_async, map_openai_model_to_claude


@dataclass
class SearchResult:
    node_id: str
    title: str
    text: str
    line_num: Optional[int]
    relevance_reason: str
    confidence: float


def format_tree_for_prompt(tree_structure: Dict[str, Any], depth: int = 0) -> str:
    """Format tree structure for LLM prompt (titles only)."""
    lines = []

    if isinstance(tree_structure, list):
        for node in tree_structure:
            lines.extend(_format_node(node, depth))
    elif isinstance(tree_structure, dict):
        if 'structure' in tree_structure:
            for node in tree_structure['structure']:
                lines.extend(_format_node(node, depth))
        else:
            lines.extend(_format_node(tree_structure, depth))

    return "\n".join(lines)


def _format_node(node: Dict[str, Any], depth: int) -> List[str]:
    """Format a single node and its children."""
    lines = []
    indent = "  " * depth
    node_id = node.get('node_id', '????')
    title = node.get('title', 'Untitled')

    lines.append(f"{indent}[{node_id}] {title}")

    if 'nodes' in node and node['nodes']:
        for child in node['nodes']:
            lines.extend(_format_node(child, depth + 1))

    return lines


def get_node_by_id(tree_structure: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
    """Find a node by its ID in the tree structure."""
    def search(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if node.get('node_id') == node_id:
            return node
        for child in node.get('nodes', []):
            result = search(child)
            if result:
                return result
        return None

    if isinstance(tree_structure, list):
        for node in tree_structure:
            result = search(node)
            if result:
                return result
    elif isinstance(tree_structure, dict):
        if 'structure' in tree_structure:
            for node in tree_structure['structure']:
                result = search(node)
                if result:
                    return result
        else:
            return search(tree_structure)

    return None


def tree_search(
    query: str,
    tree_structure: Dict[str, Any],
    doc_name: str = "document",
    max_results: int = 5,
    model: str = "sonnet"
) -> List[SearchResult]:
    """
    Search tree structure using LLM reasoning.

    Args:
        query: User's search query
        tree_structure: The tree index structure
        doc_name: Name of the document (for context)
        max_results: Maximum number of results to return
        model: LLM model to use

    Returns:
        List of SearchResult with relevant nodes
    """
    tree_outline = format_tree_for_prompt(tree_structure)

    prompt = f"""You are searching a document called "{doc_name}" to find sections relevant to this query:

QUERY: {query}

Here is the document structure (node_id in brackets):
{tree_outline}

Analyze this structure and identify which sections are MOST relevant to the query.
Consider:
1. Direct matches (section directly addresses the query)
2. Contextual matches (section provides necessary context)
3. Hierarchical relationships (parent sections that contain relevant subsections)

Return a JSON array with the top {max_results} most relevant node IDs and why they're relevant:
```json
[
  {{"node_id": "0001", "relevance_reason": "why this section is relevant", "confidence": 0.95}},
  ...
]
```

Only include sections that are genuinely relevant. If fewer than {max_results} sections are relevant, return fewer.
Return ONLY the JSON array, no other text."""

    response = claude_complete(prompt, model=model)

    try:
        start = response.find('[')
        end = response.rfind(']') + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            matches = json.loads(json_str)
        else:
            matches = json.loads(response)
    except json.JSONDecodeError:
        return []

    results = []
    for match in matches[:max_results]:
        node_id = match.get('node_id', '')
        node = get_node_by_id(tree_structure, node_id)

        if node:
            results.append(SearchResult(
                node_id=node_id,
                title=node.get('title', 'Untitled'),
                text=node.get('text', ''),
                line_num=node.get('line_num'),
                relevance_reason=match.get('relevance_reason', ''),
                confidence=match.get('confidence', 0.5)
            ))

    return results


async def tree_search_async(
    query: str,
    tree_structure: Dict[str, Any],
    doc_name: str = "document",
    max_results: int = 5,
    model: str = "sonnet"
) -> List[SearchResult]:
    """Async version of tree_search."""
    tree_outline = format_tree_for_prompt(tree_structure)

    prompt = f"""You are searching a document called "{doc_name}" to find sections relevant to this query:

QUERY: {query}

Here is the document structure (node_id in brackets):
{tree_outline}

Analyze this structure and identify which sections are MOST relevant to the query.
Consider:
1. Direct matches (section directly addresses the query)
2. Contextual matches (section provides necessary context)
3. Hierarchical relationships (parent sections that contain relevant subsections)

Return a JSON array with the top {max_results} most relevant node IDs and why they're relevant:
```json
[
  {{"node_id": "0001", "relevance_reason": "why this section is relevant", "confidence": 0.95}},
  ...
]
```

Only include sections that are genuinely relevant. If fewer than {max_results} sections are relevant, return fewer.
Return ONLY the JSON array, no other text."""

    response = await claude_complete_async(prompt, model=model)

    try:
        start = response.find('[')
        end = response.rfind(']') + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            matches = json.loads(json_str)
        else:
            matches = json.loads(response)
    except json.JSONDecodeError:
        return []

    results = []
    for match in matches[:max_results]:
        node_id = match.get('node_id', '')
        node = get_node_by_id(tree_structure, node_id)

        if node:
            results.append(SearchResult(
                node_id=node_id,
                title=node.get('title', 'Untitled'),
                text=node.get('text', ''),
                line_num=node.get('line_num'),
                relevance_reason=match.get('relevance_reason', ''),
                confidence=match.get('confidence', 0.5)
            ))

    return results


def multi_doc_search(
    query: str,
    trees: Dict[str, Dict[str, Any]],
    max_results_per_doc: int = 3,
    model: str = "sonnet"
) -> Dict[str, List[SearchResult]]:
    """
    Search across multiple document trees.

    Args:
        query: User's search query
        trees: Dict mapping doc_path to tree_structure
        max_results_per_doc: Max results per document
        model: LLM model to use

    Returns:
        Dict mapping doc_path to list of SearchResult
    """
    results = {}

    for doc_path, tree_structure in trees.items():
        doc_name = doc_path.split('/')[-1] if '/' in doc_path else doc_path
        results[doc_path] = tree_search(
            query=query,
            tree_structure=tree_structure,
            doc_name=doc_name,
            max_results=max_results_per_doc,
            model=model
        )

    return results


def format_search_results(results: List[SearchResult], include_text: bool = False) -> str:
    """Format search results for display."""
    if not results:
        return "No relevant sections found."

    lines = []
    for i, result in enumerate(results, 1):
        lines.append(f"\n{i}. [{result.node_id}] {result.title}")
        if result.line_num:
            lines.append(f"   Line: {result.line_num}")
        lines.append(f"   Relevance: {result.relevance_reason}")
        lines.append(f"   Confidence: {result.confidence:.0%}")

        if include_text and result.text:
            text_preview = result.text[:500] + "..." if len(result.text) > 500 else result.text
            lines.append(f"   Content:\n   {text_preview}")

    return "\n".join(lines)
