"""
Document Inventory - Defines which documents to index and their tiers.

Tiers:
    1. Critical - Core project docs (ROADMAP, README, core architecture)
    2. Architecture - Architecture and design docs
    3. Top Skills - Important skill files (>300 lines)
    4. Agents - Agent definition files
"""
import os
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import List, Optional, Iterator
import glob


class IndexTier(IntEnum):
    CRITICAL = 1
    ARCHITECTURE = 2
    TOP_SKILLS = 3
    AGENTS = 4


@dataclass
class DocConfig:
    path: str
    tier: IndexTier
    doc_type: str
    description: str = ""

    @property
    def relative_path(self) -> str:
        return self.path


TIER_1_CRITICAL = [
    DocConfig("ROADMAP.md", IndexTier.CRITICAL, "ROADMAP", "Project roadmap and goals"),
    DocConfig("README.md", IndexTier.CRITICAL, "README", "Project overview"),
    DocConfig("docs/ARCHITECTURE.md", IndexTier.CRITICAL, "ARCHITECTURE", "System architecture"),
    DocConfig(".claude/docs/CONTINUOUS-CLAUDE-GUIDE.md", IndexTier.CRITICAL, "DOCUMENTATION", "User guide"),
    DocConfig(".claude/docs/CONTINUOUS-CLAUDE-CHEATSHEET.md", IndexTier.CRITICAL, "DOCUMENTATION", "Quick reference"),
]

TIER_2_ARCHITECTURE = [
    DocConfig(".claude/docs/architecture/INDEX.md", IndexTier.ARCHITECTURE, "DOCUMENTATION", "Architecture index"),
    DocConfig(".claude/docs/architecture/SYSTEM-OVERVIEW.md", IndexTier.ARCHITECTURE, "ARCHITECTURE", "System diagrams"),
    DocConfig(".claude/docs/architecture/DECISION-TREES.md", IndexTier.ARCHITECTURE, "DOCUMENTATION", "Decision guidance"),
    DocConfig(".claude/docs/architecture/subsystems/memory.md", IndexTier.ARCHITECTURE, "DOCUMENTATION", "Memory subsystem"),
    DocConfig(".claude/docs/architecture/subsystems/hooks.md", IndexTier.ARCHITECTURE, "DOCUMENTATION", "Hook subsystem"),
    DocConfig(".claude/docs/architecture/subsystems/agents.md", IndexTier.ARCHITECTURE, "DOCUMENTATION", "Agent subsystem"),
    DocConfig(".claude/docs/architecture/subsystems/workflows.md", IndexTier.ARCHITECTURE, "DOCUMENTATION", "Workflow subsystem"),
    DocConfig(".claude/docs/architecture/quick-ref/agent-picker.md", IndexTier.ARCHITECTURE, "DOCUMENTATION", "Agent selection"),
    DocConfig(".claude/docs/architecture/quick-ref/hook-catalog.md", IndexTier.ARCHITECTURE, "DOCUMENTATION", "Hook catalog"),
    DocConfig(".claude/docs/architecture/quick-ref/command-ref.md", IndexTier.ARCHITECTURE, "DOCUMENTATION", "Command reference"),
    DocConfig("docs/memory-architecture.md", IndexTier.ARCHITECTURE, "ARCHITECTURE", "Memory system design"),
]

TOP_SKILLS = [
    "build", "ralph", "fix", "explore", "init-project", "maestro",
    "debug", "research", "refactor", "commit", "review",
    "tdd", "test", "migrate", "security", "hook-developer",
    "plan-mode", "skill-developer", "agentica-sdk", "knowledge-tree", "memory"
]

TOP_AGENTS = [
    "phoenix", "maestro", "kraken", "spark", "scout", "oracle",
    "architect", "arbiter", "debug-agent", "sleuth", "scribe",
    "herald", "profiler", "principal-reviewer", "principal-debugger"
]


def get_tier_1_docs() -> List[DocConfig]:
    """Get Tier 1 (Critical) documents."""
    return TIER_1_CRITICAL.copy()


def get_tier_2_docs() -> List[DocConfig]:
    """Get Tier 2 (Architecture) documents."""
    return TIER_2_ARCHITECTURE.copy()


def discover_tier_3_skills(project_root: str, min_lines: int = 300) -> List[DocConfig]:
    """Discover Tier 3 skill documents dynamically."""
    skills_dir = Path(project_root) / ".claude" / "skills"
    docs = []

    if not skills_dir.exists():
        return docs

    for skill_name in TOP_SKILLS:
        skill_file = skills_dir / skill_name / "SKILL.md"
        if skill_file.exists():
            try:
                line_count = len(skill_file.read_text(encoding="utf-8").splitlines())
                if line_count >= min_lines:
                    docs.append(DocConfig(
                        str(skill_file.relative_to(project_root)),
                        IndexTier.TOP_SKILLS,
                        "DOCUMENTATION",
                        f"{skill_name} skill ({line_count} lines)"
                    ))
            except Exception:
                pass

    # Also discover any other large skill files
    for skill_path in skills_dir.glob("*/SKILL.md"):
        skill_name = skill_path.parent.name
        if skill_name not in TOP_SKILLS:
            try:
                line_count = len(skill_path.read_text(encoding="utf-8").splitlines())
                if line_count >= min_lines:
                    docs.append(DocConfig(
                        str(skill_path.relative_to(project_root)),
                        IndexTier.TOP_SKILLS,
                        "DOCUMENTATION",
                        f"{skill_name} skill ({line_count} lines)"
                    ))
            except Exception:
                pass

    return docs


def discover_tier_4_agents(project_root: str) -> List[DocConfig]:
    """Discover Tier 4 agent definition documents."""
    agents_dir = Path(project_root) / ".claude" / "agents"
    docs = []

    if not agents_dir.exists():
        return docs

    for agent_name in TOP_AGENTS:
        agent_file = agents_dir / f"{agent_name}.md"
        if agent_file.exists():
            docs.append(DocConfig(
                str(agent_file.relative_to(project_root)),
                IndexTier.AGENTS,
                "DOCUMENTATION",
                f"{agent_name} agent definition"
            ))

    # Also discover any other agent files
    for agent_path in agents_dir.glob("*.md"):
        agent_name = agent_path.stem
        if agent_name not in TOP_AGENTS:
            docs.append(DocConfig(
                str(agent_path.relative_to(project_root)),
                IndexTier.AGENTS,
                "DOCUMENTATION",
                f"{agent_name} agent definition"
            ))

    return docs


def get_all_docs(
    project_root: str,
    tier: Optional[int] = None,
    min_skill_lines: int = 300
) -> List[DocConfig]:
    """
    Get all documents to index.

    Args:
        project_root: Project root directory
        tier: Optional tier to filter by (1-4)
        min_skill_lines: Minimum lines for skill files in Tier 3

    Returns:
        List of DocConfig objects
    """
    docs = []

    if tier is None or tier == 1:
        docs.extend(get_tier_1_docs())

    if tier is None or tier == 2:
        docs.extend(get_tier_2_docs())

    if tier is None or tier == 3:
        docs.extend(discover_tier_3_skills(project_root, min_skill_lines))

    if tier is None or tier == 4:
        docs.extend(discover_tier_4_agents(project_root))

    # Filter to only existing files
    existing_docs = []
    for doc in docs:
        full_path = Path(project_root) / doc.path
        if full_path.exists():
            existing_docs.append(doc)

    return existing_docs


def get_docs_for_init(project_root: str) -> List[DocConfig]:
    """Get documents to index during init-project (Tier 1 only)."""
    return get_all_docs(project_root, tier=1)


def format_inventory_report(docs: List[DocConfig]) -> str:
    """Format a report of documents to index."""
    lines = ["# PageIndex Document Inventory\n"]

    by_tier = {}
    for doc in docs:
        tier = doc.tier
        if tier not in by_tier:
            by_tier[tier] = []
        by_tier[tier].append(doc)

    tier_names = {
        IndexTier.CRITICAL: "Tier 1: Critical",
        IndexTier.ARCHITECTURE: "Tier 2: Architecture",
        IndexTier.TOP_SKILLS: "Tier 3: Top Skills",
        IndexTier.AGENTS: "Tier 4: Agents",
    }

    for tier in sorted(by_tier.keys()):
        lines.append(f"\n## {tier_names[tier]}\n")
        for doc in by_tier[tier]:
            lines.append(f"- `{doc.path}` - {doc.description or doc.doc_type}")

    lines.append(f"\n**Total: {len(docs)} documents**")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    project_root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    docs = get_all_docs(project_root)

    print(format_inventory_report(docs))
