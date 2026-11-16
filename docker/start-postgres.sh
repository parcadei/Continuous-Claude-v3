#!/bin/bash
# Start PostgreSQL + pgvector container for Agentica memory service
set -e

cd "$(dirname "$0")"

echo "Starting PostgreSQL + pgvector..."
docker compose up -d

echo "Waiting for PostgreSQL to be ready..."
until docker exec agentica-postgres pg_isready -U agentica -d agentica_memory > /dev/null 2>&1; do
    sleep 1
done

echo "PostgreSQL is ready!"
echo "Connection: postgresql://agentica:agentica_dev@localhost:5433/agentica_memory"
