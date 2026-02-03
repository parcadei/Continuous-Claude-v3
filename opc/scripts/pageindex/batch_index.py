#!/usr/bin/env python
"""
Batch Index - Index multiple documents in a single run.

Usage:
    python -m scripts.pageindex.batch_index --project .
    python -m scripts.pageindex.batch_index --project . --tier 1
    python -m scripts.pageindex.batch_index --project . --force
"""
import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.pageindex.doc_inventory import (
    get_all_docs,
    get_docs_for_init,
    DocConfig,
    IndexTier,
    format_inventory_report,
)
from scripts.pageindex.pageindex_service import PageIndexService, compute_doc_hash

# Lazy import to handle optional dependencies
md_to_tree = None

def _ensure_md_to_tree():
    """Lazy load md_to_tree to handle optional PyPDF2 dependency."""
    global md_to_tree
    if md_to_tree is None:
        try:
            from scripts.pageindex.pageindex.page_index_md import md_to_tree as _md_to_tree
            md_to_tree = _md_to_tree
        except ImportError as e:
            raise ImportError(
                f"PageIndex markdown parsing requires additional dependencies: {e}. "
                "Install with: pip install PyPDF2 tiktoken"
            )


@dataclass
class IndexStats:
    total: int = 0
    indexed: int = 0
    skipped: int = 0
    failed: int = 0
    duration_secs: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "indexed": self.indexed,
            "skipped": self.skipped,
            "failed": self.failed,
            "duration_secs": round(self.duration_secs, 2),
        }


async def index_document(
    service: PageIndexService,
    project_root: str,
    doc_config: DocConfig,
    force: bool = False,
    include_text: bool = True,
    verbose: bool = False,
) -> str:
    """
    Index a single document.

    Args:
        service: PageIndexService instance
        project_root: Project root path
        doc_config: Document configuration
        force: Force reindex even if unchanged
        include_text: Include full text in tree nodes
        verbose: Print detailed output

    Returns:
        Status string: "indexed", "skipped", or "failed"
    """
    doc_path = doc_config.path
    full_path = Path(project_root) / doc_path

    if not full_path.exists():
        if verbose:
            print(f"  [WARN] Not found: {doc_path}")
        return "failed"

    try:
        content = full_path.read_text(encoding="utf-8")

        # Check if reindex needed
        if not force and not service.needs_reindex(project_root, doc_path, content):
            if verbose:
                print(f"  [SKIP] Unchanged: {doc_path}")
            return "skipped"

        # Generate tree
        if verbose:
            print(f"  [INDEX] {doc_path}")

        _ensure_md_to_tree()
        tree_result = await md_to_tree(
            str(full_path),
            if_add_node_text="yes" if include_text else "no",
            if_add_node_id="yes"
        )

        # Store in database
        service.store_tree(
            project_path=project_root,
            doc_path=doc_path,
            tree_structure=tree_result,
            doc_content=content
        )

        if verbose:
            node_count = len(tree_result.get("structure", []))
            print(f"  [OK] {doc_path} ({node_count} root nodes)")

        return "indexed"

    except Exception as e:
        if verbose:
            print(f"  [FAIL] {doc_path} - {e}")
        return "failed"


async def batch_index(
    project_root: str,
    tier: Optional[int] = None,
    force: bool = False,
    include_text: bool = True,
    verbose: bool = True,
) -> IndexStats:
    """
    Index all configured documents.

    Args:
        project_root: Project root directory
        tier: Optional tier to filter by (1-4, None for all)
        force: Force reindex even if unchanged
        include_text: Include full text in tree nodes
        verbose: Print detailed output

    Returns:
        IndexStats with counts and duration
    """
    start_time = time.time()

    # Get documents to index
    docs = get_all_docs(project_root, tier=tier)
    stats = IndexStats(total=len(docs))

    if verbose:
        tier_str = f"Tier {tier}" if tier else "All tiers"
        print(f"\n[PageIndex] Batch Indexing ({tier_str})")
        print(f"   Project: {project_root}")
        print(f"   Documents: {len(docs)}")
        print("-" * 50)

    if not docs:
        if verbose:
            print("No documents found to index.")
        return stats

    # Create service
    service = PageIndexService()

    try:
        for doc in docs:
            result = await index_document(
                service=service,
                project_root=project_root,
                doc_config=doc,
                force=force,
                include_text=include_text,
                verbose=verbose,
            )

            if result == "indexed":
                stats.indexed += 1
            elif result == "skipped":
                stats.skipped += 1
            else:
                stats.failed += 1

    finally:
        service.close()

    stats.duration_secs = time.time() - start_time

    if verbose:
        print("-" * 50)
        print(f"[Done] {stats.indexed} indexed, {stats.skipped} skipped, {stats.failed} failed")
        print(f"   Duration: {stats.duration_secs:.1f}s")

    return stats


async def batch_index_for_init(
    project_root: str,
    verbose: bool = False,
) -> IndexStats:
    """
    Index documents during init-project (Tier 1 only).

    Args:
        project_root: Project root directory
        verbose: Print detailed output

    Returns:
        IndexStats with counts and duration
    """
    return await batch_index(
        project_root=project_root,
        tier=1,  # Only critical docs
        force=False,
        include_text=True,
        verbose=verbose,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Batch index documents for PageIndex",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m scripts.pageindex.batch_index --project .
    python -m scripts.pageindex.batch_index --project . --tier 1
    python -m scripts.pageindex.batch_index --project . --force --verbose
    python -m scripts.pageindex.batch_index --list
        """
    )

    parser.add_argument(
        "--project", "-p",
        default=os.getcwd(),
        help="Project root directory (default: current directory)"
    )
    parser.add_argument(
        "--tier", "-t",
        type=int,
        choices=[1, 2, 3, 4],
        help="Only index specific tier (1=Critical, 2=Architecture, 3=Skills, 4=Agents)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force reindex even if unchanged"
    )
    parser.add_argument(
        "--no-text",
        action="store_true",
        help="Don't include full text in tree nodes"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=True,
        help="Verbose output (default)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Quiet output"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List documents without indexing"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output stats as JSON"
    )

    args = parser.parse_args()

    project_root = os.path.abspath(args.project)
    verbose = not args.quiet

    if args.list:
        docs = get_all_docs(project_root, tier=args.tier)
        print(format_inventory_report(docs))
        return 0

    # Run batch indexing
    stats = asyncio.run(batch_index(
        project_root=project_root,
        tier=args.tier,
        force=args.force,
        include_text=not args.no_text,
        verbose=verbose,
    ))

    if args.json:
        import json
        print(json.dumps(stats.to_dict()))

    return 0 if stats.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
