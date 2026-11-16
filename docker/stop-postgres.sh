#!/bin/bash
# Stop PostgreSQL + pgvector container
cd "$(dirname "$0")"
docker compose down
echo "PostgreSQL stopped."
