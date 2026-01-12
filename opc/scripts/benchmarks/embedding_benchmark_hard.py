#!/usr/bin/env python3
"""
Embedding Benchmark Script - Hard Cases
========================================
Comprehensive benchmark for testing embedding model capabilities on challenging queries.

Tests cover:
1. Negation Understanding
2. Synonym/Hypernym Relationships
3. Long Context (Needle in Haystack)
4. Code Search
5. Multi-hop Reasoning
6. Temporal Queries
7. RAG-style Conceptual Queries

Usage:
    python embedding_benchmark_hard.py
    python embedding_benchmark_hard.py --models sentence-transformers/all-mpnet-base-v2
    python embedding_benchmark_hard.py --output /path/to/report.md
"""

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class BenchmarkResult:
    """Result of a single benchmark test."""
    test_name: str
    category: str
    query: str
    expected_behavior: str
    passed: bool
    score: float  # 0.0 to 1.0
    latency_ms: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResult:
    """Aggregated results for a single model."""
    model_name: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    avg_score: float = 0.0
    avg_latency_ms: float = 0.0
    category_scores: dict[str, float] = field(default_factory=dict)
    results: list[BenchmarkResult] = field(default_factory=list)


@dataclass
class CategoryMetrics:
    """Metrics for a category of tests."""
    name: str
    total: int = 0
    passed: int = 0
    avg_score: float = 0.0


# ============================================================================
# Test Data - Hard Cases
# ============================================================================

NEGATION_TESTS = [
    {
        "name": "negation_basic_password",
        "query": "authentication WITHOUT password",
        "documents": [
            ("password authentication", "HIGH"),
            ("passwordless login", "LOW"),
            ("biometric authentication", "LOW"),
            ("multi-factor authentication with password", "HIGH"),
        ],
        "expected": "Docs with 'password' should rank LOWER than passwordless alternatives",
        "description": "Basic negation - should prefer passwordLESS over password",
    },
    {
        "name": "negation_sql",
        "query": "NOT SQL database",
        "documents": [
            ("SQL database tutorial", "LOW"),
            ("PostgreSQL connection guide", "LOW"),
            ("NoSQL MongoDB example", "HIGH"),
            ("Redis key-value store", "HIGH"),
        ],
        "expected": "Non-SQL databases should rank higher than SQL docs",
        "description": "Negation with technical terms",
    },
    {
        "name": "negation_java",
        "query": "programming NOT Java",
        "documents": [
            ("Java Spring framework guide", "LOW"),
            ("Python Django tutorial", "HIGH"),
            ("JavaScript Node.js backend", "HIGH"),
            ("Java vs Python comparison", "LOW"),
        ],
        "expected": "Java-related docs should rank lower",
        "description": "Negation with common word that has multiple meanings",
    },
    {
        "name": "negation_cloud",
        "query": "deployment NOT cloud",
        "documents": [
            ("AWS deployment guide", "LOW"),
            ("Azure pipeline setup", "LOW"),
            ("on-premises server deployment", "HIGH"),
            ("container orchestration", "HIGH"),
        ],
        "expected": "Cloud deployment docs should rank lower than on-prem",
        "description": "Negation with industry terminology",
    },
]

SYNONYM_HYPERNYM_TESTS = [
    {
        "name": "hypernym_vehicle",
        "query": "vehicle",
        "documents": [
            ("car maintenance tips", "HIGH"),
            ("wheel alignment guide", "MEDIUM"),
            ("bicycle repair manual", "MEDIUM"),
            ("truck logistics company", "HIGH"),
        ],
        "expected": "car/truck > bicycle > wheel",
        "description": "Hypernym - vehicle includes car, truck, bicycle but not wheel parts",
    },
    {
        "name": "synonym_canine",
        "query": "canine",
        "documents": [
            ("dog training techniques", "HIGH"),
            ("puppy care guide", "HIGH"),
            ("feline behavior study", "LOW"),
            ("wolf habitat information", "MEDIUM"),
        ],
        "expected": "dog/puppy > wolf > feline",
        "description": "Synonym - canine is formal term for dog",
    },
    {
        "name": "hypernym_fruit",
        "query": "fruit",
        "documents": [
            ("apple orchard management", "HIGH"),
            ("orange juice recipes", "HIGH"),
            ("tree photosynthesis", "LOW"),
            ("banana bread instructions", "HIGH"),
        ],
        "expected": "apple/orange/banana > tree (not fruit)",
        "description": "Hypernym - fruit is part of tree but not the tree itself",
    },
    {
        "name": "synonym_socket",
        "query": "electrical socket",
        "documents": [
            ("power outlet installation", "HIGH"),
            ("wall plug wiring", "HIGH"),
            ("network socket programming", "LOW"),
            ("gaming socket performance", "LOW"),
        ],
        "expected": "electrical socket > network socket (different domain)",
        "description": "Polysemy - same word, different meanings",
    },
    {
        "name": "hyponym_computer",
        "query": "laptop",
        "documents": [
            ("MacBook Pro user guide", "HIGH"),
            ("Dell XPS specifications", "HIGH"),
            ("desktop PC build guide", "LOW"),
            ("tablet device review", "LOW"),
        ],
        "expected": "laptop brands > desktop > tablet",
        "description": "Hyponym - laptop is specific type of computer",
    },
]

LONG_CONTEXT_TESTS = [
    {
        "name": "needle_technical",
        "query": "What is the recommended timeout value for HTTP requests in microservices architecture when handling slow downstream services?",
        "documents": [
            # The needle - specific detail buried in text
            (
                "microservices_best_practices.txt",
                """
                When designing microservices, several best practices should be followed.
                The architecture should be loosely coupled with well-defined APIs.
                Service discovery is crucial for dynamic environments.
                For HTTP request timeouts, the recommended value is 30 seconds
                when communicating with downstream services that may have high latency.
                This timeout should be configurable per service.
                Circuit breakers should be implemented to prevent cascade failures.
                """,
                "HIGH",
            ),
            # Haystack - long unrelated technical content
            (
                "database_optimization.txt",
                """
                Database optimization is critical for application performance.
                Index design should follow query patterns observed in slow query logs.
                Connection pooling reduces overhead of establishing new connections.
                Read replicas can help distribute read load across multiple servers.
                Write-ahead logging ensures durability of database transactions.
                Normalization reduces data redundancy but may impact query performance.
                Denormalization can improve read performance at the cost of storage.
                Sharding distributes data across multiple database instances.
                Each shard contains a subset of the overall data based on a partition key.
                Horizontal scaling requires careful consideration of data locality.
                """,
                "LOW",
            ),
            (
                "frontend_caching.txt",
                """
                Frontend caching strategies improve user perceived performance.
                Browser caching reduces server load for static assets.
                Service workers enable offline capabilities for progressive web apps.
                CDN distribution reduces latency for global audiences.
                Image optimization reduces transfer sizes significantly.
                Code splitting bundles only used code for each page.
                Lazy loading defers loading of below-fold content.
                Critical CSS inlining improves first contentful paint metrics.
                """,
                "LOW",
            ),
        ],
        "expected": "Should find the 30-second timeout recommendation despite it being embedded",
        "description": "Needle in haystack - specific value in long context",
    },
    {
        "name": "needle_code",
        "query": "Where is the API key for the external service defined and how is it protected?",
        "documents": [
            (
                "config_long.txt",
                """
                # Application Configuration File
                # All settings are centralized here

                # Database Configuration
                database.host=localhost
                database.port=5432
                database.name=myapp
                database.user=admin

                # Cache Settings
                cache.enabled=true
                cache.ttl=3600

                # API Keys and Secrets
                # External service credentials are stored here
                # IMPORTANT: Never commit this file to version control
                # The EXTERNAL_SERVICE_API_KEY is loaded from environment variables
                # at runtime and never logged or exposed in error messages.
                # Rotation policy: keys must be rotated every 90 days.
                external.service.api.key=${EXTERNAL_SERVICE_API_KEY}
                external.service.endpoint=https://api.external.com

                # Feature Flags
                feature.new_ui=false
                feature.beta_features=true
                """,
                "HIGH",
            ),
        ],
        "expected": "Should identify API key location and protection measures",
        "description": "Finding specific configuration detail in config file",
    },
]

CODE_SEARCH_TESTS = [
    {
        "name": "sort_ascending",
        "query": "function that sorts list ascending",
        "documents": [
            (
                "sorting_utils.py",
                """
                def sort_list_ascending(arr):
                    '''Sort list in ascending order'''
                    return sorted(arr)

                def quick_sort(arr):
                    '''Quick sort implementation'''
                    if len(arr) <= 1:
                        return arr
                    pivot = arr[len(arr) // 2]
                    left = [x for x in arr if x < pivot]
                    middle = [x for x in arr if x == pivot]
                    right = [x for x in arr if x > pivot]
                    return left + middle + right
                """,
                "HIGH",
            ),
            (
                "list_operations.py",
                """
                def process_items(items):
                    '''Process list items'''
                    result = []
                    for item in items:
                        result.append(item * 2)
                    return result
                """,
                "LOW",
            ),
        ],
        "expected": "Should find sorted() function for ascending sort",
        "description": "Finding sorting function by behavior description",
    },
    {
        "name": "async_sync_mix",
        "query": "calling async function from sync code",
        "documents": [
            (
                "async_wrapper.py",
                """
                import asyncio

                async def fetch_data():
                    '''Async function to fetch data from API'''
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as response:
                            return await response.json()

                def sync_wrapper():
                    '''Run async function from sync context'''
                    loop = asyncio.new_event_loop()
                    try:
                        return loop.run_until_complete(fetch_data())
                    finally:
                        loop.close()
                """,
                "HIGH",
            ),
            (
                "pure_async.py",
                """
                async def main():
                    '''Main async entry point'''
                    data = await fetch_data()
                    return data
                """,
                "MEDIUM"),
        ],
        "expected": "Should find run_until_complete pattern for sync-to-async",
        "description": "Finding async-sync bridging patterns",
    },
    {
        "name": "database_connection",
        "query": "establish database connection with connection pooling",
        "documents": [
            (
                "db_connection.py",
                """
                import psycopg2
                from psycopg2 import pool

                # Create connection pool
                connection_pool = psycopg2.pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=10,
                    host='localhost',
                    database='mydb',
                    user='admin',
                    password='secret'
                )

                def get_connection():
                    '''Get connection from pool'''
                    return connection_pool.getconn()
                """,
                "HIGH",
            ),
            (
                "db_direct.py",
                """
                import psycopg2

                def connect_directly():
                    '''Connect without pooling'''
                    conn = psycopg2.connect(
                        host='localhost',
                        database='mydb',
                        user='admin',
                        password='secret'
                    )
                    return conn
                """,
                "MEDIUM",
            ),
        ],
        "expected": "Pooled connection should rank higher than direct",
        "description": "Finding connection pooling patterns",
    },
]

MULTI_HOP_TESTS = [
    {
        "name": "async_sync_chain",
        "query": "Python code that calls async function from synchronous context and handles exceptions",
        "documents": [
            (
                "async_handler.py",
                """
                import asyncio
                import logging

                async def fetch_user_data(user_id):
                    '''Fetch user data asynchronously'''
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f'/users/{user_id}') as resp:
                            return await resp.json()

                def get_user_sync(user_id):
                    '''Synchronous wrapper with exception handling'''
                    try:
                        loop = asyncio.new_event_loop()
                        try:
                            return loop.run_until_complete(fetch_user_data(user_id))
                        except asyncio.CancelledError:
                            logging.error("Request was cancelled")
                            return None
                        except Exception as e:
                            logging.error(f"Error fetching user: {e}")
                            raise
                        finally:
                            loop.close()
                    except Exception as e:
                        logging.error(f"Failed to get event loop: {e}")
                        return None
                """,
                "HIGH",
            ),
            (
                "async_simple.py",
                """
                async def fetch_data():
                    return await some_async_call()
                """,
                "LOW",
            ),
        ],
        "expected": "Must understand: async function + sync wrapper + exception handling",
        "description": "Multi-hop: requires chaining 3 concepts",
    },
    {
        "name": "auth_rate_limit",
        "query": "authentication system with rate limiting to prevent brute force attacks",
        "documents": [
            (
                "auth_service.py",
                """
                from dataclasses import dataclass
                from datetime import datetime, timedelta
                from typing import Optional
                import hashlib
                import time

                @dataclass
                class AuthResult:
                    success: bool
                    message: str
                    retry_after: Optional[int] = None

                class SecureAuthService:
                    MAX_ATTEMPTS = 5
                    WINDOW_MINUTES = 15

                    def __init__(self):
                        self.attempts: dict[str, list[datetime]] = {}

                    def _get_recent_attempts(self, username: str) -> list[datetime]:
                        cutoff = datetime.now() - timedelta(minutes=self.WINDOW_MINUTES)
                        return [t for t in self.attempts.get(username, []) if t > cutoff]

                    def authenticate(self, username: str, password: str) -> AuthResult:
                        recent = self._get_recent_attempts(username)

                        if len(recent) >= self.MAX_ATTEMPTS:
                            retry_after = int((min(recent) - cutoff).total_seconds())
                            return AuthResult(
                                success=False,
                                message="Too many attempts",
                                retry_after=60
                            )

                        if self._verify_password(username, password):
                            self.attempts[username] = []
                            return AuthResult(success=True, message="Authenticated")

                        self.attempts.setdefault(username, []).append(datetime.now())
                        return AuthResult(
                            success=False,
                            message="Invalid credentials"
                        )
                """,
                "HIGH",
            ),
        ],
        "expected": "Must connect: authentication + rate limiting + brute force prevention",
        "description": "Multi-hop: security concepts integration",
    },
]

RAG_STYLE_TESTS = [
    {
        "name": "best_practices_auth",
        "query": "What are the best practices for secure authentication?",
        "documents": [
            (
                "auth_guide.txt",
                """
                Secure authentication requires multiple layers of protection.
                Passwords should be hashed with strong algorithms like bcrypt or Argon2.
                Implement multi-factor authentication for additional security.
                Use secure session management with proper timeout policies.
                Rate limiting prevents brute force attacks on login endpoints.
                Always use HTTPS to protect credentials in transit.
                Implement proper error messages that don't reveal username existence.
                """,
                "HIGH",
            ),
            (
                "login_form.txt",
                """
                This login form accepts username and password.
                Submit button sends POST request to /login endpoint.
                Form validation ensures both fields are filled.
                """,
                "LOW",
            ),
        ],
        "expected": "Conceptual best practices should rank higher than UI description",
        "description": "RAG - conceptual vs literal matching",
    },
    {
        "name": "api_design_principles",
        "query": "How to design a RESTful API that is maintainable and scalable?",
        "documents": [
            (
                "api_design.txt",
                """
                REST API Design Principles:
                1. Use meaningful resource names with consistent naming conventions
                2. Implement proper HTTP status codes for all responses
                3. Version your API from the start (e.g., /api/v1/)
                4. Use pagination for endpoints that return collections
                5. Implement filtering and sorting at the database query level
                6. Use HATEOAS to enable discoverability
                7. Document all endpoints with OpenAPI/Swagger
                8. Implement caching strategies at appropriate layers
                """,
                "HIGH",
            ),
            (
                "api_code.txt",
                """
                @app.route('/api/users', methods=['GET'])
                def get_users():
                    return jsonify(users)
                """,
                "LOW",
            ),
        ],
        "expected": "Design principles should rank higher than code snippet",
        "description": "RAG - architectural guidance vs implementation",
    },
    {
        "name": "error_handling_patterns",
        "query": "What are effective error handling patterns in distributed systems?",
        "documents": [
            (
                "distributed_errors.txt",
                """
                Distributed System Error Handling:
                - Implement circuit breakers to prevent cascade failures
                - Use retry with exponential backoff for transient failures
                - Design for graceful degradation when dependencies fail
                - Implement dead letter queues for failed message processing
                - Use correlation IDs for distributed tracing
                - Return meaningful error codes rather than generic failures
                - Log errors with sufficient context for debugging
                - Design idempotent operations to handle duplicate requests
                """,
                "HIGH",
            ),
            (
                "try_catch.txt",
                """
                try:
                    do_something()
                except Exception as e:
                    print("Error:", e)
                """,
                "LOW",
            ),
        ],
        "expected": "Distributed patterns should rank higher than basic try-catch",
        "description": "RAG - system-level patterns vs local exception handling",
    },
]

TEMPORAL_TESTS = [
    {
        "name": "recent_change_auth",
        "query": "recent changes to authentication system",
        "documents": [
            (
                "changelog_2024_01.txt",
                """
                CHANGELOG - January 2024
                - Added two-factor authentication support
                - Updated password hashing to use Argon2
                - Fixed session timeout handling
                """,
                "HIGH",
            ),
            (
                "old_changelog.txt",
                """
                CHANGELOG - 2020
                - Initial authentication implementation
                - Basic login functionality
                - Simple session management
                """,
                "LOW",
            ),
        ],
        "expected": "Recent changelog should rank higher than old",
        "description": "Temporal - recency ranking",
    },
    {
        "name": "latest_security",
        "query": "latest security patches and vulnerabilities",
        "documents": [
            (
                "security_2024.txt",
                """
                Security Bulletin - December 2024
                CVE-2024-1234: Authentication bypass in login flow
                PATCHED: Updated validation logic in auth middleware
                Recommendation: Update to version 2.1.0 or later
                """,
                "HIGH",
            ),
            (
                "security_2022.txt",
                """
                Security Bulletin - 2022
                Old vulnerability details...
                """,
                "LOW",
            ),
        ],
        "expected": "Recent security bulletins should rank higher",
        "description": "Temporal - security update recency",
    },
]

# ============================================================================
# Embedding Model Interface
# ============================================================================

class EmbeddingModel:
    """Interface for embedding models."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        self._load_model()

    def _load_model(self):
        """Load the embedding model."""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded model: {self.model_name}")
        except ImportError:
            logger.warning("sentence-transformers not available, using mock")
            self._model = None

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode texts to embeddings."""
        start = time.perf_counter()
        if self._model is not None:
            embeddings = self._model.encode(texts, convert_to_numpy=True)
        else:
            # Mock embeddings for testing
            embeddings = np.array([self._mock_encode(t) for t in texts])
        latency = (time.perf_counter() - start) * 1000
        return embeddings, latency

    def _mock_encode(self, text: str) -> np.ndarray:
        """Generate mock embeddings for testing."""
        # Simple hash-based mock for development
        np.random.seed(hash(text) % (2**31))
        return np.random.randn(384).astype(np.float32)

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        return float(np.dot(embedding1, embedding2) / (
            np.linalg.norm(embedding1) * np.linalg.norm(embedding2) + 1e-8
        ))


class OpenAIEmbeddingModel(EmbeddingModel):
    """OpenAI embedding model wrapper."""

    def __init__(self, model_name: str = "text-embedding-3-small"):
        super().__init__(model_name)
        self._client = None

    def _load_model(self):
        """Load OpenAI client."""
        try:
            from openai import OpenAI
            self._client = OpenAI()
            logger.info(f"Loaded OpenAI model: {self.model_name}")
        except ImportError:
            logger.warning("openai package not available")
            self._client = None

    def encode(self, texts: list[str]) -> tuple[np.ndarray, float]:
        """Encode texts using OpenAI API."""
        start = time.perf_counter()
        if self._client is not None:
            response = self._client.embeddings.create(
                model=self.model_name,
                input=texts
            )
            embeddings = np.array([e.embedding for e in response.data])
        else:
            embeddings = np.array([self._mock_encode(t) for t in texts])
        latency = (time.perf_counter() - start) * 1000
        return embeddings, latency


# ============================================================================
# Benchmark Runner
# ============================================================================

class EmbeddingBenchmark:
    """Main benchmark runner for embedding models."""

    def __init__(
        self,
        models: list[str],
        output_path: Optional[Path] = None,
        verbose: bool = False
    ):
        self.models = [m.strip() for m in models]
        self.output_path = output_path
        self.verbose = verbose
        self.results: dict[str, ModelResult] = {}
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging based on verbosity."""
        if self.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

    def _run_test(
        self,
        model: EmbeddingModel,
        test: dict,
        category: str
    ) -> BenchmarkResult:
        """Run a single benchmark test."""
        query = test["query"]
        documents = test["documents"]

        # Encode query and documents
        all_texts = [query] + [doc[0] for doc in documents]
        embeddings, latency = model.encode(all_texts)

        query_embedding = embeddings[0]
        doc_embeddings = embeddings[1:]

        # Compute similarities
        similarities = [
            model.compute_similarity(query_embedding, doc_emb)
            for doc_emb in doc_embeddings
        ]

        # Evaluate ranking
        doc_info = [(doc[0], doc[1], sim) for doc, sim in zip(documents, similarities)]
        doc_info.sort(key=lambda x: x[2], reverse=True)

        # Calculate score based on expected ranking
        expected_order = self._get_expected_order(documents)
        actual_order = [doc[1] for doc in doc_info]

        score = self._calculate_ranking_score(expected_order, actual_order)

        # Determine pass/fail
        passed = score >= 0.7

        return BenchmarkResult(
            test_name=test["name"],
            category=category,
            query=query,
            expected_behavior=test["expected"],
            passed=passed,
            score=score,
            latency_ms=latency / len(documents),  # per-document latency
            details={
                "similarities": {doc[0][:30]: sim for doc, sim in zip(documents, similarities)},
                "expected_order": expected_order,
                "actual_order": actual_order,
            }
        )

    def _get_expected_order(self, documents: list[tuple[str, str]]) -> list[str]:
        """Get expected ranking order from document expected levels."""
        level_priority = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        return [doc[1] for doc in sorted(documents, key=lambda d: level_priority[d[1]])]

    def _calculate_ranking_score(
        self,
        expected_order: list[str],
        actual_order: list[str]
    ) -> float:
        """Calculate normalized ranking score (0-1)."""
        if not expected_order or len(expected_order) != len(actual_order):
            return 0.0

        # NDCG-style scoring
        ideal_gains = [3 if lvl == "HIGH" else 2 if lvl == "MEDIUM" else 1
                      for lvl in expected_order]
        actual_gains = [3 if lvl == "HIGH" else 2 if lvl == "MEDIUM" else 1
                       for lvl in actual_order]

        # Compute NDCG
        dcg = sum(g / np.log2(i + 2) for i, g in enumerate(actual_gains))
        idcg = sum(g / np.log2(i + 2) for i, g in enumerate(ideal_gains))

        return dcg / idcg if idcg > 0 else 0.0

    def run_all_tests(self) -> dict[str, ModelResult]:
        """Run all benchmark tests for all models."""
        all_tests = self._get_all_tests()

        for model_name in self.models:
            logger.info(f"Testing model: {model_name}")
            model_result = ModelResult(model_name=model_name)

            # Detect model type and load appropriate wrapper
            if "openai" in model_name.lower() or model_name.startswith("text-"):
                model = OpenAIEmbeddingModel(model_name)
            else:
                model = EmbeddingModel(model_name)

            for category, tests in all_tests.items():
                category_metrics = CategoryMetrics(name=category)
                model_result.total_tests += len(tests)

                for test in tests:
                    result = self._run_test(model, test, category)
                    model_result.results.append(result)

                    if result.passed:
                        model_result.passed += 1
                        category_metrics.passed += 1

                    category_metrics.total += 1
                    category_metrics.avg_score += result.score

                # Calculate category average
                if category_metrics.total > 0:
                    category_metrics.avg_score /= category_metrics.total
                    model_result.category_scores[category] = category_metrics.avg_score

            # Calculate overall metrics
            if model_result.results:
                model_result.avg_score = np.mean([r.score for r in model_result.results])
                model_result.avg_latency_ms = np.mean([r.latency_ms for r in model_result.results])
                model_result.failed = model_result.total_tests - model_result.passed

            self.results[model_name] = model_result

        return self.results

    def _get_all_tests(self) -> dict[str, list[dict]]:
        """Get all benchmark tests organized by category."""
        return {
            "negation": NEGATION_TESTS,
            "synonym_hypernym": SYNONYM_HYPERNYM_TESTS,
            "long_context": LONG_CONTEXT_TESTS,
            "code_search": CODE_SEARCH_TESTS,
            "multi_hop": MULTI_HOP_TESTS,
            "rag_style": RAG_STYLE_TESTS,
            "temporal": TEMPORAL_TESTS,
        }

    def generate_report(self) -> str:
        """Generate markdown report of benchmark results."""
        if not self.results:
            return "No results to report."

        lines = [
            "# Embedding Model Benchmark Report",
            f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"\n**Models Tested:** {', '.join(self.results.keys())}",
            "\n---\n",
            "## Executive Summary",
            "\n| Model | Tests | Passed | Failed | Avg Score | Avg Latency |",
            "|-------|-------|--------|--------|-----------|-------------|",
        ]

        for result in self.results.values():
            status = "PASS" if result.failed == 0 else "PARTIAL" if result.passed > 0 else "FAIL"
            lines.append(
                f"| {result.model_name} | {result.total_tests} | "
                f"{result.passed} | {result.failed} | "
                f"{result.avg_score:.3f} | {result.avg_latency_ms:.1f}ms |"
            )

        # Category breakdown
        lines.extend([
            "\n---\n",
            "## Category Performance",
            "\n| Model | " + " | ".join(self._get_all_tests().keys()) + " |",
            "| " + "--- | " * (len(self._get_all_tests()) + 1),
        ])

        for result in self.results.values():
            scores = [
                f"{result.category_scores.get(cat, 0):.2f}"
                for cat in self._get_all_tests().keys()
            ]
            lines.append(f"| {result.model_name} | " + " | ".join(scores) + " |")

        # Detailed results per category
        for category in self._get_all_tests().keys():
            lines.extend([
                "\n---\n",
                f"## {category.upper().replace('_', ' ')} Tests",
            ])

            for result in self.results.values():
                category_results = [r for r in result.results if r.category == category]
                if not category_results:
                    continue

                lines.append(f"\n### {result.model_name}")

                for r in category_results:
                    status = "PASS" if r.passed else "FAIL"
                    lines.append(f"\n#### {r.test_name} [{status}]")
                    lines.append(f"- **Query:** `{r.query[:80]}..." if len(r.query) > 80 else f"- **Query:** `{r.query}`")
                    lines.append(f"- **Expected:** {r.expected_behavior}")
                    lines.append(f"- **Score:** {r.score:.3f}")
                    lines.append(f"- **Latency:** {r.latency_ms:.1f}ms")

                    if not r.passed:
                        lines.append(f"- **Similarities:** {r.details.get('similarities', {})}")

        # Recommendations
        lines.extend([
            "\n---\n",
            "## Recommendations",
            "\nBased on benchmark results:\n",
        ])

        # Find best model per category
        best_per_category = {}
        for category in self._get_all_tests().keys():
            best_score = 0
            best_model = None
            for result in self.results.values():
                score = result.category_scores.get(category, 0)
                if score > best_score:
                    best_score = score
                    best_model = result.model_name
            if best_model:
                best_per_category[category] = (best_model, best_score)

        for category, (model, score) in best_per_category.items():
            lines.append(f"- **{category}:** Use {model} (score: {score:.2f})")

        # Overall best
        best_overall = max(self.results.values(), key=lambda r: r.avg_score)
        lines.append(f"\n- **Overall:** {best_overall.model_name} (avg score: {best_overall.avg_score:.3f})")

        return "\n".join(lines)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Embedding Model Benchmark - Hard Cases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python embedding_benchmark_hard.py
    python embedding_benchmark_hard.py --models sentence-transformers/all-mpnet-base-v2
    python embedding_benchmark_hard.py --models sentence-transformers/all-mpnet-base-v2 text-embedding-3-small --output report.md
        """
    )

    parser.add_argument(
        "--models",
        nargs="+",
        default=["sentence-transformers/all-mpnet-base-v2"],
        help="Embedding models to benchmark"
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output path for markdown report"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    # Run benchmark
    benchmark = EmbeddingBenchmark(
        models=args.models,
        output_path=args.output,
        verbose=args.verbose
    )

    logger.info(f"Starting benchmark with models: {args.models}")
    results = benchmark.run_all_tests()

    # Generate and output report
    report = benchmark.generate_report()

    if args.json:
        # Convert results to JSON-serializable format
        json_results = {
            model_name: {
                "total_tests": r.total_tests,
                "passed": r.passed,
                "failed": r.failed,
                "avg_score": r.avg_score,
                "avg_latency_ms": r.avg_latency_ms,
                "category_scores": r.category_scores,
                "tests": [
                    {
                        "name": t.test_name,
                        "category": t.category,
                        "passed": t.passed,
                        "score": t.score,
                        "latency_ms": t.latency_ms,
                    }
                    for t in r.results
                ]
            }
            for model_name, r in results.items()
        }
        print(json.dumps(json_results, indent=2))
    else:
        print(report)

    # Save report if output path specified
    if args.output:
        args.output.write_text(report)
        logger.info(f"Report saved to: {args.output}")

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for model_name, result in results.items():
        status = "PASS" if result.failed == 0 else "PARTIAL" if result.passed > 0 else "FAIL"
        print(f"\n{model_name}:")
        print(f"  Status: {status}")
        print(f"  Passed: {result.passed}/{result.total_tests}")
        print(f"  Avg Score: {result.avg_score:.3f}")
        print(f"  Avg Latency: {result.avg_latency_ms:.1f}ms")


if __name__ == "__main__":
    main()
