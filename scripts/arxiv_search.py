#!/usr/bin/env python3
"""
arXiv Search - Search and retrieve academic papers from arXiv.

USAGE:
    # Search for papers
    uv run python scripts/arxiv_search.py search "machine learning" --max 10

    # Get paper by ID
    uv run python scripts/arxiv_search.py get 2301.00001

    # Generate BibTeX citation
    uv run python scripts/arxiv_search.py bibtex 2301.00001

    # Search with filters
    uv run python scripts/arxiv_search.py search "neural networks" --category cs.AI --sort submittedDate

API Reference: https://info.arxiv.org/help/api/basics.html
"""

import argparse
import json
import re
import sys
from typing import Any

import feedparser
import requests

# arXiv API endpoint
ARXIV_API_URL = "http://export.arxiv.org/api/query"


def extract_arxiv_id(url_or_id: str) -> str:
    """Extract arXiv paper ID from URL or raw ID.

    Args:
        url_or_id: Either a full arXiv URL or just the ID

    Returns:
        Clean arXiv ID without version suffix (e.g., "2301.00001")
    """
    # Handle full URLs like http://arxiv.org/abs/2301.00001v1
    if "/" in url_or_id:
        url_or_id = url_or_id.split("/")[-1]

    # Remove version suffix (v1, v2, etc.)
    return re.sub(r'v\d+$', '', url_or_id)


def clean_title(title: str) -> str:
    """Clean paper title by removing newlines and extra spaces.

    Args:
        title: Raw title string

    Returns:
        Cleaned title string
    """
    return re.sub(r'\s+', ' ', title).strip()


def search_arxiv(
    query: str,
    max_results: int = 10,
    sort_by: str = "relevance",
    sort_order: str = "descending",
    category: str | None = None
) -> dict[str, Any]:
    """Search arXiv for papers matching query.

    Args:
        query: Search query string
        max_results: Maximum number of results to return
        sort_by: Sort field (relevance, lastUpdatedDate, submittedDate)
        sort_order: Sort order (ascending, descending)
        category: Optional category filter (e.g., cs.AI, cs.LG)

    Returns:
        Dict with "papers" list and optional "error" message
    """
    if not query or not query.strip():
        return {"papers": [], "error": "Query cannot be empty"}

    # Build search query with optional category filter
    search_query = f"all:{query}"
    if category:
        search_query = f"({search_query}) AND cat:{category}"

    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }

    try:
        response = requests.get(ARXIV_API_URL, params=params, timeout=30)
        response.raise_for_status()

        feed = feedparser.parse(response.text)
        papers = []

        for entry in feed.entries[:max_results]:
            paper = _parse_entry(entry)
            papers.append(paper)

        return {"papers": papers, "error": None}

    except Exception as e:
        return {"papers": [], "error": str(e)}


def get_paper(paper_id: str) -> dict[str, Any]:
    """Get paper metadata by arXiv ID.

    Args:
        paper_id: arXiv paper ID (e.g., "2301.00001")

    Returns:
        Dict with paper metadata and optional "error" message
    """
    if not paper_id or not paper_id.strip():
        return {"error": "Paper ID cannot be empty"}

    # Clean the ID in case it has version suffix
    clean_id = extract_arxiv_id(paper_id)

    params = {
        "id_list": clean_id,
    }

    try:
        response = requests.get(ARXIV_API_URL, params=params, timeout=30)
        response.raise_for_status()

        feed = feedparser.parse(response.text)

        if not feed.entries:
            return {"error": f"Paper not found: {clean_id}"}

        paper = _parse_entry(feed.entries[0])
        paper["error"] = None
        return paper

    except Exception as e:
        return {"error": str(e)}


def _parse_entry(entry: Any) -> dict[str, Any]:
    """Parse a feedparser entry into a paper dict.

    Args:
        entry: feedparser entry object

    Returns:
        Dict with paper metadata
    """
    # Extract paper ID from URL
    paper_id = extract_arxiv_id(entry.id)

    # Extract authors
    authors = [author.name for author in getattr(entry, 'authors', [])]

    # Extract PDF URL
    pdf_url = None
    for link in getattr(entry, 'links', []):
        if link.get('title') == 'pdf':
            pdf_url = link.get('href')
            break

    # Extract primary category
    category = None
    if hasattr(entry, 'arxiv_primary_category'):
        category = entry.arxiv_primary_category.get('term')

    return {
        "id": paper_id,
        "title": clean_title(entry.title),
        "authors": authors,
        "summary": entry.summary,
        "published": entry.published,
        "updated": getattr(entry, 'updated', entry.published),
        "pdf_url": pdf_url,
        "abs_url": entry.id,
        "category": category,
    }


def generate_bibtex(paper: dict[str, Any]) -> str:
    """Generate BibTeX citation for a paper.

    Args:
        paper: Paper metadata dict with id, title, authors, published

    Returns:
        BibTeX formatted citation string
    """
    # Extract year from published date
    year = paper.get("published", "")[:4]

    # Generate citation key from first author's last name and year
    authors = paper.get("authors", [])
    if authors:
        # Get first author's last name (handle "Last, First" or "First Last" format)
        first_author = authors[0]
        if "," in first_author:
            last_name = first_author.split(",")[0].strip()
        else:
            last_name = first_author.split()[-1]
        # Clean for BibTeX key (alphanumeric only)
        last_name = re.sub(r'[^a-zA-Z]', '', last_name).lower()
    else:
        last_name = "unknown"

    citation_key = f"{last_name}{year}_{paper['id'].replace('.', '_')}"

    # Escape LaTeX special characters in title
    title = paper.get("title", "")
    title = title.replace("&", "\\&")
    title = title.replace("%", "\\%")
    title = title.replace("_", "\\_")

    # Format authors for BibTeX (join with " and ")
    if len(authors) > 1:
        author_str = " and ".join(authors)
    else:
        author_str = authors[0] if authors else "Unknown"

    # Build BibTeX entry
    bibtex = f"""@article{{{citation_key},
  author    = {{{author_str}}},
  title     = {{{title}}},
  journal   = {{arXiv preprint arXiv:{paper['id']}}},
  year      = {{{year}}},
  eprint    = {{{paper['id']}}},
  archiveprefix = {{arXiv}},
  primaryclass = {{{paper.get('category', 'cs.LG')}}}
}}"""

    return bibtex


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Search and retrieve papers from arXiv",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s search "machine learning" --max 10
  %(prog)s get 2301.00001
  %(prog)s bibtex 2301.00001
  %(prog)s search "transformers" --category cs.AI --sort submittedDate
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for papers")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--max", type=int, default=10,
        help="Maximum number of results (default: 10)"
    )
    search_parser.add_argument(
        "--sort", choices=["relevance", "lastUpdatedDate", "submittedDate"],
        default="relevance",
        help="Sort by field (default: relevance)"
    )
    search_parser.add_argument(
        "--category", help="Filter by category (e.g., cs.AI, cs.LG, math.CO)"
    )

    # Get command
    get_parser = subparsers.add_parser("get", help="Get paper by ID")
    get_parser.add_argument("paper_id", help="arXiv paper ID (e.g., 2301.00001)")

    # BibTeX command
    bibtex_parser = subparsers.add_parser("bibtex", help="Generate BibTeX citation")
    bibtex_parser.add_argument("paper_id", help="arXiv paper ID (e.g., 2301.00001)")

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    if not args.command:
        print("Error: Please specify a command (search, get, or bibtex)")
        print("Use --help for usage information")
        sys.exit(1)

    if args.command == "search":
        result = search_arxiv(
            args.query,
            max_results=args.max,
            sort_by=args.sort,
            category=args.category
        )

        if result["error"]:
            print(f"Error: {result['error']}")
            sys.exit(1)

        print(f"Found {len(result['papers'])} papers:\n")
        for paper in result["papers"]:
            print(f"ID: {paper['id']}")
            print(f"Title: {paper['title']}")
            print(f"Authors: {', '.join(paper['authors'])}")
            print(f"Category: {paper['category']}")
            print(f"Published: {paper['published'][:10]}")
            print(f"PDF: {paper['pdf_url']}")
            print("-" * 60)

        # Also output JSON for programmatic use
        print("\n--- JSON Output ---")
        print(json.dumps(result, indent=2))

    elif args.command == "get":
        result = get_paper(args.paper_id)

        if result.get("error"):
            print(f"Error: {result['error']}")
            sys.exit(1)

        print(f"Title: {result['title']}")
        print(f"Authors: {', '.join(result['authors'])}")
        print(f"Published: {result['published'][:10]}")
        print(f"Category: {result['category']}")
        print(f"\nAbstract:\n{result['summary']}")
        print(f"\nPDF: {result['pdf_url']}")

        # Also output JSON
        print("\n--- JSON Output ---")
        print(json.dumps(result, indent=2))

    elif args.command == "bibtex":
        # First get the paper
        paper = get_paper(args.paper_id)

        if paper.get("error"):
            print(f"Error: {paper['error']}")
            sys.exit(1)

        bibtex = generate_bibtex(paper)
        print(bibtex)


if __name__ == "__main__":
    main()
