#!/usr/bin/env python3
"""
USAGE: Upload documents to Ragie for RAG.

Examples:
    # Upload a single PDF
    uv run python scripts/ragie_upload.py --file ~/books/decision-theory.pdf

    # Upload with partition (for organizing by subject)
    uv run python scripts/ragie_upload.py --file ~/books/modal-logic.pdf --partition modal-logic

    # Upload with metadata
    uv run python scripts/ragie_upload.py --file ~/books/game-theory.pdf --metadata '{"author": "von Neumann", "subject": "decision-theory"}'

    # Upload all PDFs in a directory
    uv run python scripts/ragie_upload.py --dir ~/books/decision-theory/ --partition decision-theory
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx


def upload_file(file_path: Path, partition: str | None, metadata: dict | None, api_key: str) -> dict:
    """Upload a single file to Ragie."""
    url = "https://api.ragie.ai/documents"
    headers = {"Authorization": f"Bearer {api_key}"}

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/pdf")}
        data = {}
        if partition:
            data["partition"] = partition
        if metadata:
            data["metadata"] = json.dumps(metadata)

        response = httpx.post(url, headers=headers, files=files, data=data, timeout=300.0)
        response.raise_for_status()
        return response.json()


def main():
    parser = argparse.ArgumentParser(description="Upload documents to Ragie")
    parser.add_argument("--file", type=str, help="Path to a single file to upload")
    parser.add_argument("--dir", type=str, help="Path to directory of files to upload")
    parser.add_argument("--partition", type=str, help="Partition name to organize documents")
    parser.add_argument("--metadata", type=str, help="JSON metadata to attach to documents")
    parser.add_argument("--extension", type=str, default=".pdf", help="File extension filter for --dir (default: .pdf)")
    args = parser.parse_args()

    api_key = os.environ.get("RAGIE_API_KEY")
    if not api_key:
        print("Error: RAGIE_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    if not args.file and not args.dir:
        print("Error: Must specify --file or --dir", file=sys.stderr)
        sys.exit(1)

    metadata = json.loads(args.metadata) if args.metadata else None

    files_to_upload = []
    if args.file:
        files_to_upload.append(Path(args.file).expanduser())
    if args.dir:
        dir_path = Path(args.dir).expanduser()
        files_to_upload.extend(dir_path.glob(f"*{args.extension}"))

    results = []
    for file_path in files_to_upload:
        if not file_path.exists():
            print(f"Warning: {file_path} does not exist, skipping", file=sys.stderr)
            continue

        print(f"Uploading {file_path.name}...", file=sys.stderr)
        try:
            result = upload_file(file_path, args.partition, metadata, api_key)
            results.append({"file": str(file_path), "status": "success", "document_id": result.get("id")})
            print(f"  ✓ Uploaded: {result.get('id')}", file=sys.stderr)
        except Exception as e:
            results.append({"file": str(file_path), "status": "error", "error": str(e)})
            print(f"  ✗ Failed: {e}", file=sys.stderr)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
