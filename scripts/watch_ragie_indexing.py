#!/usr/bin/env python3
"""
Watch Ragie document indexing status.
Polls every 30 seconds until all documents are ready.

Usage:
    uv run python scripts/watch_ragie_indexing.py --partition process-algebra
    uv run python scripts/watch_ragie_indexing.py --doc-ids id1,id2,id3
"""

import argparse
import os
import sys
import time
import requests
from datetime import datetime

def get_api_key():
    key = os.environ.get('RAGIE_API_KEY')
    if not key:
        # Try loading from .env
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith('RAGIE_API_KEY='):
                        key = line.split('=', 1)[1].strip()
                        break
    return key

def check_documents(api_key: str, doc_ids: list[str] | None = None, partition: str | None = None) -> dict:
    """Check status of documents. Returns {id: status} dict."""
    headers = {'Authorization': f'Bearer {api_key}'}

    if doc_ids:
        # Check specific documents
        results = {}
        for doc_id in doc_ids:
            resp = requests.get(f'https://api.ragie.ai/documents/{doc_id}', headers=headers)
            if resp.status_code == 200:
                doc = resp.json()
                results[doc_id] = {
                    'status': doc.get('status', 'unknown'),
                    'name': doc.get('name', 'unknown')[:40]
                }
            else:
                results[doc_id] = {'status': 'error', 'name': 'fetch failed'}
        return results

    elif partition:
        # List documents in partition
        resp = requests.get(
            'https://api.ragie.ai/documents',
            headers=headers,
            params={'partition': partition}
        )
        if resp.status_code == 200:
            docs = resp.json().get('documents', [])
            return {
                d['id']: {
                    'status': d.get('status', 'unknown'),
                    'name': d.get('name', 'unknown')[:40]
                }
                for d in docs
            }

    return {}

def main():
    parser = argparse.ArgumentParser(description='Watch Ragie indexing status')
    parser.add_argument('--partition', default='process-algebra', help='Partition to watch')
    parser.add_argument('--doc-ids', help='Comma-separated document IDs')
    parser.add_argument('--interval', type=int, default=30, help='Poll interval in seconds')
    parser.add_argument('--timeout', type=int, default=600, help='Max wait time in seconds')
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print('ERROR: RAGIE_API_KEY not found in env or .env')
        sys.exit(1)

    doc_ids = args.doc_ids.split(',') if args.doc_ids else None
    start = time.time()

    print(f'[{datetime.now().strftime("%H:%M:%S")}] Watching partition: {args.partition}')
    print(f'Polling every {args.interval}s, timeout {args.timeout}s\n')

    while True:
        elapsed = time.time() - start
        if elapsed > args.timeout:
            print(f'\nTIMEOUT after {args.timeout}s')
            sys.exit(1)

        results = check_documents(api_key, doc_ids, args.partition)

        all_ready = True
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Status check:')
        for doc_id, info in results.items():
            status = info['status']
            name = info['name']
            icon = '✓' if status == 'ready' else '⏳' if status in ['partitioning', 'pending'] else '✗'
            print(f'  {icon} {name}: {status}')
            if status != 'ready':
                all_ready = False

        if all_ready and results:
            print(f'\n✓ All {len(results)} documents ready!')
            print('READY')  # Signal for automation
            sys.exit(0)

        print(f'\nWaiting {args.interval}s... ({int(elapsed)}s elapsed)')
        time.sleep(args.interval)

if __name__ == '__main__':
    main()
