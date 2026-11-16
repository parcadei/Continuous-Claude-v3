#!/usr/bin/env python3
"""
USAGE: Check document processing status in Ragie.

Examples:
    # Check specific document
    uv run python scripts/ragie_status.py --doc-id 8a5a0ae8-9c83-49b0-83cf-562032a863ea

    # List all documents
    uv run python scripts/ragie_status.py --list

    # List documents in partition
    uv run python scripts/ragie_status.py --list --partition decision-theory
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv
import httpx

load_dotenv()


def get_document(doc_id: str, api_key: str) -> dict:
    """Get document status."""
    url = f"https://api.ragie.ai/documents/{doc_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = httpx.get(url, headers=headers, timeout=30.0)
    response.raise_for_status()
    return response.json()


def list_documents(partition: str | None, api_key: str) -> dict:
    """List all documents."""
    url = "https://api.ragie.ai/documents"
    headers = {"Authorization": f"Bearer {api_key}"}
    if partition:
        headers["partition"] = partition
    response = httpx.get(url, headers=headers, timeout=30.0)
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="Check Ragie document status")
    parser.add_argument("--doc-id", type=str, help="Document ID to check")
    parser.add_argument("--list", action="store_true", help="List all documents")
    parser.add_argument("--partition", type=str, help="Filter by partition")
    args = parser.parse_args()

    api_key = os.environ.get("RAGIE_API_KEY")
    if not api_key:
        print("Error: RAGIE_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    try:
        if args.doc_id:
            result = get_document(args.doc_id, api_key)
            status = result.get("status", "unknown")
            name = result.get("name", "unknown")
            print(f"Document: {name}")
            print(f"Status: {status}")
            print(f"Full response: {json.dumps(result, indent=2)}")
        elif args.list:
            result = list_documents(args.partition, api_key)
            docs = result.get("documents", [])
            print(f"Found {len(docs)} documents:")
            for doc in docs:
                status = doc.get("status", "?")
                name = doc.get("name", "?")
                doc_id = doc.get("id", "?")
                print(f"  [{status}] {name} ({doc_id})")
        else:
            print("Specify --doc-id or --list", file=sys.stderr)
            sys.exit(1)

    except httpx.HTTPStatusError as e:
        print(f"Error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
