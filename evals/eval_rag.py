from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import httpx
from braintrust import Eval


API_URL = os.getenv("API_URL", "http://localhost:8000")


def load_data():
    dataset_path = Path(__file__).parent / "dataset.jsonl"
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        yield row["input"], row["expected"]


def task(inp: Dict[str, Any]) -> Dict[str, Any]:
    q = inp["query"]
    resp = httpx.post(f"{API_URL}/query", json={"query": q}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def score_has_sources(expected: Dict[str, Any], output: Dict[str, Any]) -> float:
    return 1.0 if output.get("sources") else 0.0


def score_has_warnings_field(expected: Dict[str, Any], output: Dict[str, Any]) -> float:
    return 1.0 if isinstance(output.get("warnings"), list) else 0.0


def score_has_tools_field(expected: Dict[str, Any], output: Dict[str, Any]) -> float:
    return 1.0 if isinstance(output.get("tools"), list) else 0.0


def score_keyword_in_sources(expected: Dict[str, Any], output: Dict[str, Any]) -> float:
    keywords = expected.get("must_contain_any", []) or []
    ctx_text = " ".join([c.get("text", "") for c in (output.get("sources") or [])])
    ctx_text_l = ctx_text.lower()
    return 1.0 if any(k.lower() in ctx_text_l for k in keywords) else 0.0


Eval(
    "Creta Emergency Assistant — Prototype v1",
    data=load_data,
    task=task,
    scores=[
        score_has_sources,
        score_has_warnings_field,
        score_has_tools_field,
        score_keyword_in_sources,
    ],
)
