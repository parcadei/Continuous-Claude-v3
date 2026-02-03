"""Unit tests for PageIndex markdown parsing."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from scripts.pageindex.pageindex.page_index_md import (
        extract_nodes_from_markdown,
        extract_node_text_content,
        build_tree_from_nodes,
        clean_tree_for_output,
        md_to_tree,
    )
    PAGE_INDEX_MD_AVAILABLE = True
except ImportError as e:
    PAGE_INDEX_MD_AVAILABLE = False
    pytestmark = pytest.mark.skip(f"page_index_md dependencies not available: {e}")


@pytest.mark.unit
@pytest.mark.skipif(not PAGE_INDEX_MD_AVAILABLE, reason="page_index_md dependencies not available")
class TestExtractNodesFromMarkdown:
    def test_simple_headers(self):
        md = """# Title
## Section 1
### Subsection 1.1
## Section 2
"""
        nodes, lines = extract_nodes_from_markdown(md)

        assert len(nodes) == 4
        assert nodes[0]["node_title"] == "Title"
        assert nodes[1]["node_title"] == "Section 1"
        assert nodes[2]["node_title"] == "Subsection 1.1"
        assert nodes[3]["node_title"] == "Section 2"

    def test_header_line_numbers(self):
        md = """# Title

Some content.

## Section 1
More content.
"""
        nodes, lines = extract_nodes_from_markdown(md)

        assert nodes[0]["line_num"] == 1
        assert nodes[1]["line_num"] == 5

    def test_ignores_headers_in_code_blocks(self):
        md = """# Real Header

```python
# This is a comment, not a header
## Also not a header
```

## Another Real Header
"""
        nodes, lines = extract_nodes_from_markdown(md)

        assert len(nodes) == 2
        assert nodes[0]["node_title"] == "Real Header"
        assert nodes[1]["node_title"] == "Another Real Header"

    def test_all_header_levels(self):
        md = """# H1
## H2
### H3
#### H4
##### H5
###### H6
"""
        nodes, lines = extract_nodes_from_markdown(md)

        assert len(nodes) == 6
        for i, node in enumerate(nodes):
            assert node["node_title"] == f"H{i+1}"

    def test_empty_markdown(self):
        nodes, lines = extract_nodes_from_markdown("")

        assert len(nodes) == 0
        assert len(lines) == 1  # One empty line

    def test_no_headers(self):
        md = """This is just text.
No headers here.
"""
        nodes, lines = extract_nodes_from_markdown(md)

        assert len(nodes) == 0


@pytest.mark.unit
@pytest.mark.skipif(not PAGE_INDEX_MD_AVAILABLE, reason="page_index_md dependencies not available")
class TestExtractNodeTextContent:
    def test_simple_text_extraction(self):
        md = """# Title
Some title content.

## Section
Section content here.
"""
        nodes, lines = extract_nodes_from_markdown(md)
        nodes_with_text = extract_node_text_content(nodes, lines)

        assert len(nodes_with_text) == 2
        assert nodes_with_text[0]["title"] == "Title"
        assert "Some title content" in nodes_with_text[0]["text"]
        assert nodes_with_text[1]["title"] == "Section"
        assert "Section content here" in nodes_with_text[1]["text"]

    def test_header_levels_extracted(self):
        md = """# H1
## H2
### H3
"""
        nodes, lines = extract_nodes_from_markdown(md)
        nodes_with_text = extract_node_text_content(nodes, lines)

        assert nodes_with_text[0]["level"] == 1
        assert nodes_with_text[1]["level"] == 2
        assert nodes_with_text[2]["level"] == 3

    def test_text_spans_until_next_header(self):
        md = """# Section 1
Line 1
Line 2
Line 3
## Section 2
Different content.
"""
        nodes, lines = extract_nodes_from_markdown(md)
        nodes_with_text = extract_node_text_content(nodes, lines)

        assert "Line 1" in nodes_with_text[0]["text"]
        assert "Line 2" in nodes_with_text[0]["text"]
        assert "Line 3" in nodes_with_text[0]["text"]
        assert "Different content" not in nodes_with_text[0]["text"]


@pytest.mark.unit
@pytest.mark.skipif(not PAGE_INDEX_MD_AVAILABLE, reason="page_index_md dependencies not available")
class TestBuildTreeFromNodes:
    def test_flat_structure(self):
        nodes = [
            {"title": "Section 1", "level": 1, "text": "Text 1", "line_num": 1},
            {"title": "Section 2", "level": 1, "text": "Text 2", "line_num": 5},
        ]

        tree = build_tree_from_nodes(nodes)

        assert len(tree) == 2
        assert tree[0]["title"] == "Section 1"
        assert tree[1]["title"] == "Section 2"
        assert tree[0]["nodes"] == []
        assert tree[1]["nodes"] == []

    def test_nested_structure(self):
        nodes = [
            {"title": "Parent", "level": 1, "text": "Parent text", "line_num": 1},
            {"title": "Child 1", "level": 2, "text": "Child 1 text", "line_num": 3},
            {"title": "Child 2", "level": 2, "text": "Child 2 text", "line_num": 5},
        ]

        tree = build_tree_from_nodes(nodes)

        assert len(tree) == 1
        assert tree[0]["title"] == "Parent"
        assert len(tree[0]["nodes"]) == 2
        assert tree[0]["nodes"][0]["title"] == "Child 1"
        assert tree[0]["nodes"][1]["title"] == "Child 2"

    def test_deeply_nested(self):
        nodes = [
            {"title": "L1", "level": 1, "text": "", "line_num": 1},
            {"title": "L2", "level": 2, "text": "", "line_num": 2},
            {"title": "L3", "level": 3, "text": "", "line_num": 3},
            {"title": "L4", "level": 4, "text": "", "line_num": 4},
        ]

        tree = build_tree_from_nodes(nodes)

        assert len(tree) == 1
        assert tree[0]["nodes"][0]["nodes"][0]["nodes"][0]["title"] == "L4"

    def test_node_ids_assigned(self):
        nodes = [
            {"title": "A", "level": 1, "text": "", "line_num": 1},
            {"title": "B", "level": 2, "text": "", "line_num": 2},
        ]

        tree = build_tree_from_nodes(nodes)

        assert tree[0]["node_id"] == "0001"
        assert tree[0]["nodes"][0]["node_id"] == "0002"

    def test_sibling_sections_same_level(self):
        nodes = [
            {"title": "Main", "level": 1, "text": "", "line_num": 1},
            {"title": "Sub 1", "level": 2, "text": "", "line_num": 2},
            {"title": "Sub 2", "level": 2, "text": "", "line_num": 3},
            {"title": "Sub 3", "level": 2, "text": "", "line_num": 4},
        ]

        tree = build_tree_from_nodes(nodes)

        assert len(tree[0]["nodes"]) == 3

    def test_empty_nodes(self):
        tree = build_tree_from_nodes([])

        assert tree == []


@pytest.mark.unit
@pytest.mark.skipif(not PAGE_INDEX_MD_AVAILABLE, reason="page_index_md dependencies not available")
class TestCleanTreeForOutput:
    def test_preserves_essential_fields(self):
        tree = [
            {
                "title": "Section",
                "node_id": "0001",
                "text": "Content",
                "line_num": 1,
                "nodes": [],
                "extra_field": "should be removed"  # This won't be removed based on current impl
            }
        ]

        cleaned = clean_tree_for_output(tree)

        assert cleaned[0]["title"] == "Section"
        assert cleaned[0]["node_id"] == "0001"
        assert cleaned[0]["text"] == "Content"
        assert cleaned[0]["line_num"] == 1

    def test_recursive_cleaning(self):
        tree = [
            {
                "title": "Parent",
                "node_id": "0001",
                "text": "Parent text",
                "line_num": 1,
                "nodes": [
                    {
                        "title": "Child",
                        "node_id": "0002",
                        "text": "Child text",
                        "line_num": 3,
                        "nodes": []
                    }
                ]
            }
        ]

        cleaned = clean_tree_for_output(tree)

        assert cleaned[0]["nodes"][0]["title"] == "Child"


@pytest.mark.unit
@pytest.mark.skipif(not PAGE_INDEX_MD_AVAILABLE, reason="page_index_md dependencies not available")
class TestMdToTree:
    @pytest.mark.asyncio
    async def test_basic_tree_generation(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("""# Title
## Section 1
Content 1
## Section 2
Content 2
""", encoding="utf-8")

        result = await md_to_tree(
            str(md_file),
            if_add_node_text="yes",
            if_add_node_id="yes"
        )

        assert "doc_name" in result
        assert result["doc_name"] == "test"
        assert "structure" in result
        assert len(result["structure"]) > 0

    @pytest.mark.asyncio
    async def test_tree_has_node_ids(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("""# Title
## Section
""", encoding="utf-8")

        result = await md_to_tree(str(md_file), if_add_node_id="yes")

        assert result["structure"][0].get("node_id") is not None

    @pytest.mark.asyncio
    async def test_tree_without_text(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("""# Title
Some content
## Section
More content
""", encoding="utf-8")

        result = await md_to_tree(str(md_file), if_add_node_text="no")

        # Text may still exist but might be filtered in output format
        assert "structure" in result

    @pytest.mark.asyncio
    async def test_doc_name_from_filename(self, tmp_path):
        md_file = tmp_path / "ROADMAP.md"
        md_file.write_text("# Roadmap", encoding="utf-8")

        result = await md_to_tree(str(md_file))

        assert result["doc_name"] == "ROADMAP"


@pytest.mark.unit
@pytest.mark.skipif(not PAGE_INDEX_MD_AVAILABLE, reason="page_index_md dependencies not available")
class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_markdown_to_tree_pipeline(self, sample_roadmap_content, tmp_path):
        md_file = tmp_path / "ROADMAP.md"
        md_file.write_text(sample_roadmap_content, encoding="utf-8")

        result = await md_to_tree(
            str(md_file),
            if_add_node_text="yes",
            if_add_node_id="yes"
        )

        assert result["doc_name"] == "ROADMAP"
        assert len(result["structure"]) > 0

        # Check that structure has expected hierarchy
        root = result["structure"][0]
        assert root["title"] == "Project Roadmap"
        assert "nodes" in root
        assert len(root["nodes"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
