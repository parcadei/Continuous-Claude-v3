#!/usr/bin/env python
"""
PageIndex CLI - Command-line interface for PageIndex tree-based RAG.

Commands:
    generate <file>     Create tree index from markdown file
    search <query>      Search indexed documents using tree reasoning
    list                List all indexed documents
    rebuild             Re-index all documents
    show <doc_path>     Show tree structure for a document
"""
import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.pageindex.pageindex_service import (
    PageIndexService, DocType, compute_project_id
)
from scripts.pageindex.tree_search import (
    tree_search, format_search_results, format_tree_for_prompt
)
from scripts.pageindex.pageindex.page_index_md import md_to_tree


def get_project_root() -> str:
    """Get project root from current directory or env."""
    return os.getenv("PROJECT_ROOT", os.getcwd())


def cmd_generate(args):
    """Generate tree index from markdown file."""
    file_path = Path(args.file).resolve()

    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return 1

    if not file_path.suffix.lower() in ['.md', '.markdown']:
        print(f"Error: File must be markdown (.md or .markdown)")
        return 1

    project_root = get_project_root()
    try:
        doc_path = str(file_path.relative_to(project_root))
    except ValueError:
        doc_path = file_path.name

    print(f"Generating tree index for: {file_path}")
    print(f"Project: {project_root}")
    print(f"Doc path: {doc_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    tree_result = asyncio.run(md_to_tree(
        str(file_path),
        if_thinning=args.thin,
        min_token_threshold=args.min_tokens if args.thin else None,
        if_add_node_text='yes' if args.include_text else 'no',
        if_add_node_id='yes'
    ))

    service = PageIndexService()
    try:
        index = service.store_tree(
            project_path=project_root,
            doc_path=doc_path,
            tree_structure=tree_result,
            doc_content=content
        )
        print(f"\nTree index stored:")
        print(f"  ID: {index.id}")
        print(f"  Type: {index.doc_type.value}")
        print(f"  Hash: {index.doc_hash[:16]}...")

        if args.show_tree:
            print(f"\nTree structure:")
            print(format_tree_for_prompt(tree_result))

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(tree_result, f, indent=2)
            print(f"\nTree saved to: {args.output}")

    finally:
        service.close()

    return 0


def cmd_search(args):
    """Search indexed documents."""
    project_root = get_project_root()

    service = PageIndexService()
    try:
        if args.doc:
            tree_index = service.get_tree(project_root, args.doc)
            if not tree_index:
                print(f"Error: No index found for {args.doc}")
                return 1
            trees = {args.doc: tree_index.tree_structure}
        else:
            all_trees = service.list_trees(project_path=project_root)
            if not all_trees:
                print("No indexed documents found. Run 'pageindex generate' first.")
                return 1

            trees = {}
            for t in all_trees:
                full_tree = service.get_tree(project_root, t.doc_path)
                if full_tree:
                    trees[t.doc_path] = full_tree.tree_structure

        print(f"Searching {len(trees)} document(s) for: {args.query}")
        print("-" * 50)

        for doc_path, tree_struct in trees.items():
            results = tree_search(
                query=args.query,
                tree_structure=tree_struct,
                doc_name=doc_path,
                max_results=args.limit,
                model=args.model
            )

            if results:
                print(f"\n📄 {doc_path}:")
                print(format_search_results(results, include_text=args.include_text))

    finally:
        service.close()

    return 0


def cmd_list(args):
    """List indexed documents."""
    project_root = get_project_root() if not args.all else None

    service = PageIndexService()
    try:
        doc_type = DocType[args.type.upper()] if args.type else None
        trees = service.list_trees(project_path=project_root, doc_type=doc_type)

        if not trees:
            print("No indexed documents found.")
            return 0

        print(f"Found {len(trees)} indexed document(s):\n")

        for tree in trees:
            print(f"📄 {tree.doc_path}")
            print(f"   Type: {tree.doc_type.value}")
            print(f"   Nodes: {tree.tree_structure.get('node_count', '?')}")
            print(f"   Updated: {tree.updated_at}")
            if args.verbose and tree.doc_hash:
                print(f"   Hash: {tree.doc_hash[:16]}...")
            print()

    finally:
        service.close()

    return 0


def cmd_show(args):
    """Show tree structure for a document."""
    project_root = get_project_root()

    service = PageIndexService()
    try:
        tree_index = service.get_tree(project_root, args.doc_path)

        if not tree_index:
            print(f"Error: No index found for {args.doc_path}")
            return 1

        if args.json:
            print(json.dumps(tree_index.tree_structure, indent=2))
        else:
            print(f"📄 {args.doc_path}")
            print(f"Type: {tree_index.doc_type.value}")
            print(f"Updated: {tree_index.updated_at}")
            print(f"\nTree structure:")
            print(format_tree_for_prompt(tree_index.tree_structure))

    finally:
        service.close()

    return 0


def cmd_rebuild(args):
    """Rebuild indexes for all documents."""
    project_root = get_project_root()

    service = PageIndexService()
    try:
        trees = service.list_trees(project_path=project_root)

        if not trees:
            print("No indexed documents to rebuild.")
            return 0

        print(f"Rebuilding {len(trees)} document(s)...")

        for tree in trees:
            doc_path = Path(project_root) / tree.doc_path

            if not doc_path.exists():
                print(f"⚠️  Skipping {tree.doc_path} (file not found)")
                continue

            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if not args.force and not service.needs_reindex(project_root, tree.doc_path, content):
                print(f"⏭️  Skipping {tree.doc_path} (unchanged)")
                continue

            print(f"🔄 Rebuilding {tree.doc_path}...")

            tree_result = asyncio.run(md_to_tree(
                str(doc_path),
                if_add_node_text='yes',
                if_add_node_id='yes'
            ))

            service.store_tree(
                project_path=project_root,
                doc_path=tree.doc_path,
                tree_structure=tree_result,
                doc_content=content
            )
            print(f"✅ {tree.doc_path}")

        print("\nRebuild complete.")

    finally:
        service.close()

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="PageIndex CLI - Tree-based RAG for markdown documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    pageindex generate ROADMAP.md
    pageindex search "current project goals"
    pageindex list
    pageindex show ROADMAP.md
    pageindex rebuild --force
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    gen_parser = subparsers.add_parser("generate", help="Generate tree index from markdown")
    gen_parser.add_argument("file", help="Markdown file to index")
    gen_parser.add_argument("--thin", action="store_true", help="Apply tree thinning")
    gen_parser.add_argument("--min-tokens", type=int, default=100, help="Min tokens for thinning")
    gen_parser.add_argument("--include-text", action="store_true", help="Include full text in index")
    gen_parser.add_argument("--show-tree", action="store_true", help="Show tree structure after indexing")
    gen_parser.add_argument("--output", "-o", help="Save tree to JSON file")

    search_parser = subparsers.add_parser("search", help="Search indexed documents")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--doc", "-d", help="Search specific document only")
    search_parser.add_argument("--limit", "-l", type=int, default=5, help="Max results per document")
    search_parser.add_argument("--model", "-m", default="sonnet", help="LLM model (sonnet/haiku)")
    search_parser.add_argument("--include-text", "-t", action="store_true", help="Include node text in results")

    list_parser = subparsers.add_parser("list", help="List indexed documents")
    list_parser.add_argument("--all", "-a", action="store_true", help="List from all projects")
    list_parser.add_argument("--type", "-t", help="Filter by doc type")
    list_parser.add_argument("--verbose", "-v", action="store_true", help="Show more details")

    show_parser = subparsers.add_parser("show", help="Show tree structure")
    show_parser.add_argument("doc_path", help="Document path")
    show_parser.add_argument("--json", action="store_true", help="Output as JSON")

    rebuild_parser = subparsers.add_parser("rebuild", help="Rebuild all indexes")
    rebuild_parser.add_argument("--force", "-f", action="store_true", help="Rebuild even if unchanged")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "generate": cmd_generate,
        "search": cmd_search,
        "list": cmd_list,
        "show": cmd_show,
        "rebuild": cmd_rebuild,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
