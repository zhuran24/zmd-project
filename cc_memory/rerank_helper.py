#!/usr/bin/env python3
"""Isolated Qwen reranker helper for cc_memory.

mem.py shells out to this script so the main CLI never imports torch or
sentence-transformers. stdin is JSON, stdout is JSON.
"""
from __future__ import annotations

import gc
import json
import os
import sys
import traceback
from typing import Any

os.environ.setdefault("HF_HOME", r"E:\caches\huggingface")
os.environ.setdefault("HF_HUB_CACHE", os.path.join(os.environ["HF_HOME"], "hub"))
os.environ.setdefault("HF_XET_CACHE", os.path.join(os.environ["HF_HOME"], "xet"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

DEFAULT_MODEL = "Qwen/Qwen3-Reranker-0.6B"
DEFAULT_INSTRUCTION = (
    "Given a project collaboration memory draft, retrieve existing memory nodes that are directly "
    "related, depended on, or mentioned by the draft."
)


def load_model(model_name: str, device: str, instruction: str) -> Any:
    from sentence_transformers import CrossEncoder

    return CrossEncoder(
        model_name,
        device=device,
        prompts={"cc_memory": instruction},
        default_prompt_name="cc_memory",
        local_files_only=True,
    )


def as_scores(value: Any) -> list[float]:
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (int, float)):
        return [float(value)]
    if not isinstance(value, list):
        raise ValueError(f"unexpected score output type: {type(value).__name__}")
    scores: list[float] = []
    for item in value:
        if isinstance(item, list):
            if len(item) != 1:
                raise ValueError("unexpected nested score output")
            item = item[0]
        scores.append(float(item))
    return scores


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        query = payload.get("query")
        docs = payload.get("docs")
        if not isinstance(query, str):
            raise ValueError("payload.query must be a string")
        if not isinstance(docs, list) or not all(isinstance(doc, str) for doc in docs):
            raise ValueError("payload.docs must be a list of strings")
        model_name = str(payload.get("model") or DEFAULT_MODEL)
        instruction = str(payload.get("instruction") or DEFAULT_INSTRUCTION)
        batch_size = int(payload.get("batch_size") or 8)

        if not docs:
            print(json.dumps({"scores": []}, ensure_ascii=False, separators=(",", ":")))
            return 0

        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = None
        try:
            model = load_model(model_name, device, instruction)
            pairs = [(query, doc) for doc in docs]
            raw_scores = model.predict(
                pairs,
                batch_size=batch_size,
                show_progress_bar=False,
                activation_fn=torch.nn.Sigmoid(),
            )
            scores = as_scores(raw_scores)
            if len(scores) != len(docs):
                raise ValueError(f"reranker returned {len(scores)} scores for {len(docs)} docs")
            print(json.dumps({"scores": scores}, ensure_ascii=False, separators=(",", ":")))
            return 0
        finally:
            if model is not None:
                del model
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    except BaseException as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
