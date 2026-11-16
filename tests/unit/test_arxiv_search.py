"""Tests for arXiv Search Script - TDD First."""

import pytest
from unittest.mock import patch, Mock, MagicMock

# Sample arXiv API XML response for testing
SAMPLE_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title type="html">ArXiv Query: all:machine learning</title>
  <id>http://arxiv.org/api/query</id>
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">1000</opensearch:totalResults>
  <opensearch:startIndex xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</opensearch:startIndex>
  <opensearch:itemsPerPage xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">5</opensearch:itemsPerPage>
  <entry>
    <id>http://arxiv.org/abs/2301.00001v1</id>
    <updated>2023-01-01T00:00:00Z</updated>
    <published>2023-01-01T00:00:00Z</published>
    <title>Machine Learning for Scientific Discovery</title>
    <summary>This paper explores machine learning applications in science.</summary>
    <author><name>Smith, John</name></author>
    <author><name>Doe, Jane</name></author>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
    <link href="http://arxiv.org/abs/2301.00001v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2301.00001v1" rel="related" type="application/pdf"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2301.00002v2</id>
    <updated>2023-01-02T00:00:00Z</updated>
    <published>2023-01-02T00:00:00Z</published>
    <title>Deep Learning Advances</title>
    <summary>Recent advances in deep learning architectures.</summary>
    <author><name>Brown, Alice</name></author>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
    <link href="http://arxiv.org/abs/2301.00002v2" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2301.00002v2" rel="related" type="application/pdf"/>
  </entry>
</feed>
"""

SAMPLE_ARXIV_SINGLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title type="html">ArXiv Query: id_list=2301.00001</title>
  <id>http://arxiv.org/api/query</id>
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">1</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2301.00001v1</id>
    <updated>2023-01-01T00:00:00Z</updated>
    <published>2023-01-01T00:00:00Z</published>
    <title>Machine Learning for Scientific Discovery</title>
    <summary>This paper explores machine learning applications in science. We present novel methods for applying ML to various scientific domains.</summary>
    <author><name>Smith, John</name></author>
    <author><name>Doe, Jane</name></author>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
    <link href="http://arxiv.org/abs/2301.00001v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2301.00001v1" rel="related" type="application/pdf"/>
  </entry>
</feed>
"""

SAMPLE_ARXIV_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title type="html">ArXiv Query: all:xyznonexistent123</title>
  <id>http://arxiv.org/api/query</id>
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</opensearch:totalResults>
</feed>
"""


class TestArxivSearch:
    """Test the search_arxiv function."""

    @patch('requests.get')
    def test_search_returns_results(self, mock_get):
        """Search should return papers with expected fields."""
        mock_response = Mock()
        mock_response.text = SAMPLE_ARXIV_XML
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.arxiv_search import search_arxiv
        result = search_arxiv("machine learning", max_results=5)

        assert "papers" in result
        assert len(result["papers"]) == 2  # Two entries in sample
        assert result["error"] is None

    @patch('requests.get')
    def test_search_paper_has_required_fields(self, mock_get):
        """Each paper should have id, title, authors, summary, pdf_url."""
        mock_response = Mock()
        mock_response.text = SAMPLE_ARXIV_XML
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.arxiv_search import search_arxiv
        result = search_arxiv("machine learning", max_results=5)

        paper = result["papers"][0]
        assert "id" in paper
        assert "title" in paper
        assert "authors" in paper
        assert "summary" in paper
        assert "pdf_url" in paper
        assert "published" in paper
        assert "category" in paper

    @patch('requests.get')
    def test_search_extracts_id_correctly(self, mock_get):
        """Paper ID should be extracted without version suffix."""
        mock_response = Mock()
        mock_response.text = SAMPLE_ARXIV_XML
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.arxiv_search import search_arxiv
        result = search_arxiv("machine learning", max_results=5)

        # Should extract "2301.00001" from "http://arxiv.org/abs/2301.00001v1"
        assert result["papers"][0]["id"] == "2301.00001"

    @patch('requests.get')
    def test_search_respects_max_results(self, mock_get):
        """Search should respect max_results parameter."""
        mock_response = Mock()
        mock_response.text = SAMPLE_ARXIV_XML
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.arxiv_search import search_arxiv
        result = search_arxiv("machine learning", max_results=1)

        # Should only return 1 paper
        assert len(result["papers"]) <= 1

    def test_search_invalid_query(self):
        """Empty query should return error."""
        from scripts.arxiv_search import search_arxiv
        result = search_arxiv("")

        assert result["error"] is not None
        assert "query" in result["error"].lower()

    @patch('requests.get')
    def test_search_handles_empty_results(self, mock_get):
        """Search with no results should return empty list."""
        mock_response = Mock()
        mock_response.text = SAMPLE_ARXIV_EMPTY
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.arxiv_search import search_arxiv
        result = search_arxiv("xyznonexistent123", max_results=5)

        assert result["papers"] == []
        assert result["error"] is None

    @patch('requests.get')
    def test_search_handles_network_error(self, mock_get):
        """Network errors should be caught and returned."""
        mock_get.side_effect = Exception("Network error")

        from scripts.arxiv_search import search_arxiv
        result = search_arxiv("machine learning", max_results=5)

        assert result["error"] is not None
        assert "papers" in result
        assert result["papers"] == []

    @patch('requests.get')
    def test_search_uses_correct_api_params(self, mock_get):
        """Search should call API with correct parameters."""
        mock_response = Mock()
        mock_response.text = SAMPLE_ARXIV_XML
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.arxiv_search import search_arxiv
        search_arxiv("quantum computing", max_results=10, sort_by="submittedDate")

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        params = call_args[1]["params"]
        assert params["search_query"] == "all:quantum computing"
        assert params["max_results"] == 10
        assert params["sortBy"] == "submittedDate"


class TestArxivGet:
    """Test the get_paper function."""

    @patch('requests.get')
    def test_get_by_id(self, mock_get):
        """Get paper by ID should return paper metadata."""
        mock_response = Mock()
        mock_response.text = SAMPLE_ARXIV_SINGLE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.arxiv_search import get_paper
        result = get_paper("2301.00001")

        assert "title" in result
        assert "authors" in result
        assert "summary" in result
        assert "id" in result
        assert result["error"] is None

    @patch('requests.get')
    def test_get_returns_full_abstract(self, mock_get):
        """Get paper should return full abstract/summary."""
        mock_response = Mock()
        mock_response.text = SAMPLE_ARXIV_SINGLE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.arxiv_search import get_paper
        result = get_paper("2301.00001")

        # Summary should be complete, not truncated
        assert "novel methods" in result["summary"]

    def test_get_invalid_id(self):
        """Invalid paper ID should return error."""
        from scripts.arxiv_search import get_paper
        result = get_paper("")

        assert result["error"] is not None

    @patch('requests.get')
    def test_get_not_found(self, mock_get):
        """Non-existent paper should return appropriate error."""
        mock_response = Mock()
        mock_response.text = SAMPLE_ARXIV_EMPTY
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.arxiv_search import get_paper
        result = get_paper("9999.99999")

        assert result["error"] is not None or result.get("title") is None

    @patch('requests.get')
    def test_get_uses_id_list_param(self, mock_get):
        """Get should use id_list parameter, not search_query."""
        mock_response = Mock()
        mock_response.text = SAMPLE_ARXIV_SINGLE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.arxiv_search import get_paper
        get_paper("2301.00001")

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        params = call_args[1]["params"]
        assert "id_list" in params
        assert params["id_list"] == "2301.00001"


class TestBibtex:
    """Test the generate_bibtex function."""

    def test_generate_bibtex_basic(self):
        """Generate BibTeX should produce valid citation."""
        from scripts.arxiv_search import generate_bibtex

        paper = {
            "id": "2301.00001",
            "title": "Test Paper",
            "authors": ["Smith, John", "Doe, Jane"],
            "published": "2023-01-01T00:00:00Z",
            "category": "cs.LG"
        }
        bibtex = generate_bibtex(paper)

        assert "@article{" in bibtex
        assert "2301.00001" in bibtex
        assert "Smith" in bibtex
        assert "Test Paper" in bibtex

    def test_generate_bibtex_includes_year(self):
        """BibTeX should include publication year."""
        from scripts.arxiv_search import generate_bibtex

        paper = {
            "id": "2301.00001",
            "title": "Test Paper",
            "authors": ["Smith, John"],
            "published": "2023-01-01T00:00:00Z",
            "category": "cs.LG"
        }
        bibtex = generate_bibtex(paper)

        assert "2023" in bibtex

    def test_generate_bibtex_escapes_special_chars(self):
        """BibTeX should escape LaTeX special characters."""
        from scripts.arxiv_search import generate_bibtex

        paper = {
            "id": "2301.00001",
            "title": "Machine Learning & Neural Networks: A Study",
            "authors": ["O'Brien, Patrick"],
            "published": "2023-01-01T00:00:00Z",
            "category": "cs.LG"
        }
        bibtex = generate_bibtex(paper)

        # & should be escaped as \&
        assert "\\&" in bibtex or "&" not in bibtex.split("title")[1].split("}")[0]

    def test_generate_bibtex_handles_single_author(self):
        """BibTeX should handle single author."""
        from scripts.arxiv_search import generate_bibtex

        paper = {
            "id": "2301.00001",
            "title": "Solo Work",
            "authors": ["Smith, John"],
            "published": "2023-01-01T00:00:00Z",
            "category": "cs.LG"
        }
        bibtex = generate_bibtex(paper)

        assert "Smith" in bibtex
        assert " and " not in bibtex  # Single author, no "and"

    def test_generate_bibtex_multiple_authors(self):
        """BibTeX should join multiple authors with 'and'."""
        from scripts.arxiv_search import generate_bibtex

        paper = {
            "id": "2301.00001",
            "title": "Collaborative Work",
            "authors": ["Smith, John", "Doe, Jane", "Brown, Alice"],
            "published": "2023-01-01T00:00:00Z",
            "category": "cs.LG"
        }
        bibtex = generate_bibtex(paper)

        assert " and " in bibtex

    def test_generate_bibtex_citation_key_format(self):
        """Citation key should be based on first author and year."""
        from scripts.arxiv_search import generate_bibtex

        paper = {
            "id": "2301.00001",
            "title": "Test Paper",
            "authors": ["Smith, John"],
            "published": "2023-01-01T00:00:00Z",
            "category": "cs.LG"
        }
        bibtex = generate_bibtex(paper)

        # Should have format like @article{smith2023_2301.00001, or similar
        assert "@article{" in bibtex


class TestArxivSearchCLI:
    """Test CLI argument parsing."""

    def test_cli_search_command(self):
        """CLI should support search command."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, 'argv', ['arxiv_search.py', 'search', 'quantum computing', '--max', '5']):
            from scripts.arxiv_search import parse_args
            args = parse_args()

            assert args.command == "search"
            assert args.query == "quantum computing"
            assert args.max == 5

    def test_cli_get_command(self):
        """CLI should support get command."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, 'argv', ['arxiv_search.py', 'get', '2301.00001']):
            from scripts.arxiv_search import parse_args
            args = parse_args()

            assert args.command == "get"
            assert args.paper_id == "2301.00001"

    def test_cli_bibtex_command(self):
        """CLI should support bibtex command."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, 'argv', ['arxiv_search.py', 'bibtex', '2301.00001']):
            from scripts.arxiv_search import parse_args
            args = parse_args()

            assert args.command == "bibtex"
            assert args.paper_id == "2301.00001"

    def test_cli_search_sort_option(self):
        """CLI search should support sort option."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, 'argv', ['arxiv_search.py', 'search', 'ml', '--sort', 'submittedDate']):
            from scripts.arxiv_search import parse_args
            args = parse_args()

            assert args.sort == "submittedDate"

    def test_cli_search_category_filter(self):
        """CLI search should support category filter."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, 'argv', ['arxiv_search.py', 'search', 'neural', '--category', 'cs.AI']):
            from scripts.arxiv_search import parse_args
            args = parse_args()

            assert args.category == "cs.AI"


class TestHelperFunctions:
    """Test helper/utility functions."""

    def test_extract_arxiv_id(self):
        """Extract ID from various arXiv URL formats."""
        from scripts.arxiv_search import extract_arxiv_id

        # Standard format
        assert extract_arxiv_id("http://arxiv.org/abs/2301.00001v1") == "2301.00001"
        assert extract_arxiv_id("http://arxiv.org/abs/2301.00001v2") == "2301.00001"

        # Without version
        assert extract_arxiv_id("http://arxiv.org/abs/2301.00001") == "2301.00001"

        # Just ID
        assert extract_arxiv_id("2301.00001") == "2301.00001"
        assert extract_arxiv_id("2301.00001v1") == "2301.00001"

    def test_clean_title(self):
        """Title should have newlines removed and be stripped."""
        from scripts.arxiv_search import clean_title

        assert clean_title("Test\n  Title") == "Test Title"
        assert clean_title("  Spaces  ") == "Spaces"
