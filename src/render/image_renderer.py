"""Optional image-render wrapper around the main grid visualizer."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.render.grid_visualizer import render_from_json as render_heatmap_from_json


def render_from_json(json_path: Path, output_path: Optional[Path] = None):
    return render_heatmap_from_json(json_path, output_path=output_path)
