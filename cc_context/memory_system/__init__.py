"""Typed memory graph system for cc_context/memory.

The package keeps Markdown as the human editing surface, but moves the machine
truth into typed nodes, typed edges, events, and change transactions.
"""

from .frontmatter import split_frontmatter, parse_frontmatter, extract_wikilinks
from .graph import build_graph, MemoryGraph

__all__ = [
    "split_frontmatter",
    "parse_frontmatter",
    "extract_wikilinks",
    "build_graph",
    "MemoryGraph",
]
