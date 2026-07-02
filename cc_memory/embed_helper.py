#!/usr/bin/env python3
"""Isolated sentence-transformers embedding helper for cc_memory.

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

DEFAULT_MODEL = "microsoft/harrier-oss-v1-0.6b"


def harrier_model(model_name: str) -> bool:
    return model_name == DEFAULT_MODEL or "harrier" in model_name.lower()


def tokenizer_kwargs_for(model_name: str) -> dict[str, Any]:
    if harrier_model(model_name):
        return {"fix_mistral_regex": True}
    return {}


def query_prompt_for(model_name: str) -> str | None:
    if harrier_model(model_name):
        return "web_search_query"
    return None


def load_model(model_name: str, device: str) -> tuple[Any, dict[str, Any]]:
    from sentence_transformers import SentenceTransformer

    attempts = [
        {"dtype": "auto"},
        {"torch_dtype": "float16"},
        {"dtype": "float16"},
        {},
    ]
    tokenizer_kwargs = tokenizer_kwargs_for(model_name)
    last_error: BaseException | None = None
    for model_kwargs in attempts:
        try:
            kwargs: dict[str, Any] = {"device": device, "model_kwargs": model_kwargs}
            if tokenizer_kwargs:
                kwargs["tokenizer_kwargs"] = tokenizer_kwargs
            return SentenceTransformer(model_name, **kwargs), model_kwargs
        except BaseException as exc:
            last_error = exc
            print(f"LOAD_ATTEMPT_FAILED model_kwargs={model_kwargs}: {exc}", file=sys.stderr, flush=True)
    assert last_error is not None
    raise last_error


def normalize(array: Any) -> Any:
    import numpy as np

    arr = np.asarray(array, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def encode_texts(model: Any, texts: list[str], *, mode: str, model_name: str, batch_size: int) -> Any:
    # Normalization is applied once by normalize() on the result (with zero-vector
    # protection); do not also ask the encoder to normalize.
    encode_kwargs = {
        "batch_size": batch_size,
        "convert_to_numpy": True,
        "show_progress_bar": False,
    }
    prompt_name = query_prompt_for(model_name) if mode == "query" else None
    if prompt_name:
        if hasattr(model, "encode_query"):
            try:
                return model.encode_query(texts, prompt_name=prompt_name, **encode_kwargs)
            except TypeError:
                pass
        try:
            return model.encode(texts, prompt_name=prompt_name, **encode_kwargs)
        except (KeyError, ValueError) as exc:
            print(
                f"PROMPT_FALLBACK prompt_name={prompt_name!r} unavailable ({exc}); encoding without prompt",
                file=sys.stderr,
                flush=True,
            )
    return model.encode(texts, **encode_kwargs)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        texts = payload.get("texts")
        if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
            raise ValueError("payload.texts must be a list of strings")
        mode = str(payload.get("mode") or "doc")
        if mode not in {"doc", "query"}:
            raise ValueError("payload.mode must be 'doc' or 'query'")
        model_name = str(payload.get("model") or DEFAULT_MODEL)
        batch_size = int(payload.get("batch_size") or 8)

        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = None
        try:
            model, used_model_kwargs = load_model(model_name, device)
            vectors = normalize(encode_texts(model, texts, mode=mode, model_name=model_name, batch_size=batch_size))
            dim = int(vectors.shape[1]) if len(texts) else 0
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "model": model_name,
                        "mode": mode,
                        "dim": dim,
                        "dtype": "float32",
                        "normalize": 1,
                        "device": device,
                        "used_model_kwargs": used_model_kwargs,
                        "vectors": vectors.astype("float32").tolist(),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
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
