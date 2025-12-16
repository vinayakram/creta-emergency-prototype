from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import httpx
from dotenv import load_dotenv

# Load environment variables (.env)
load_dotenv()

# Toggle Braintrust (OFF by default)
USE_BRAINTRUST = os.getenv("USE_BRAINTRUST", "0") == "1"

if USE_BRAINTRUST:
    from braintrust import Eval

API_URL = os.getenv("API_URL", "http://localhost:8000")


# ---------------------------------------------------------------------
# Dataset loader
# ---------------------------------------------------------------------
def load_data():
    dataset_path = Path(__file__).parent / "dataset.jsonl"
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        yield {
            "input": row["input"],
            "expected": row["expected"],
        }


# ---------------------------------------------------------------------
# Task under evaluation (RAG API)
# ---------------------------------------------------------------------
def task(datum: Dict[str, Any]) -> Dict[str, Any]:
    query = datum["input"]["query"]
    resp = httpx.post(
        f"{API_URL}/query",
        json={"query": query},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------
def score_has_sources(expected: Dict[str, Any], output: Dict[str, Any]) -> float:
    return 1.0 if output.get("sources") else 0.0


def score_has_warnings_field(expected: Dict[str, Any], output: Dict[str, Any]) -> float:
    return 1.0 if isinstance(output.get("warnings"), list) else 0.0


def score_has_tools_field(expected: Dict[str, Any], output: Dict[str, Any]) -> float:
    return 1.0 if isinstance(output.get("tools"), list) else 0.0


def score_keyword_in_sources(expected: Dict[str, Any], output: Dict[str, Any]) -> float:
    keywords = expected.get("must_contain_any", []) or []
    ctx_text = " ".join(
        c.get("text", "") for c in (output.get("sources") or [])
    ).lower()
    return 1.0 if any(k.lower() in ctx_text for k in keywords) else 0.0


# 🔥 Negative test: context mixing
def score_no_context_mixing(expected: Dict[str, Any], output: Dict[str, Any]) -> float:
    forbidden = expected.get("must_not_contain_any", []) or []

    combined_text = " ".join(
        [
            *output.get("steps", []),
            *output.get("warnings", []),
            *[c.get("text", "") for c in (output.get("sources") or [])],
        ]
    ).lower()

    return 0.0 if any(w.lower() in combined_text for w in forbidden) else 1.0


# 🔥 Quality test: minimum answer depth
def score_min_steps(expected: Dict[str, Any], output: Dict[str, Any]) -> float:
    min_steps = expected.get("min_steps")
    if min_steps is None:
        return 1.0

    steps = output.get("steps") or []
    return 1.0 if len(steps) >= min_steps else 0.0


# ---------------------------------------------------------------------
# Run evals
# ---------------------------------------------------------------------
if USE_BRAINTRUST:
    Eval(
        "Creta Emergency Assistant — Prototype v1",
        data=load_data,
        task=task,
        scores=[
            score_has_sources,
            score_has_warnings_field,
            score_has_tools_field,
            score_keyword_in_sources,
            score_no_context_mixing,
            score_min_steps,
        ],
    )
else:
    # -----------------------------------------------------------------
    # Local evaluation runner with FULL TRACEABILITY
    # -----------------------------------------------------------------
    for datum in load_data():
        output = task(datum)

        print("\n" + "=" * 80)
        print("QUERY:")
        print(datum["input"]["query"])

        print("\nMODEL OUTPUT:")

        print("\nSTEPS:")
        for i, step in enumerate(output.get("steps", []), 1):
            print(f"  {i}. {step}")

        print("\nWARNINGS:")
        for w in output.get("warnings", []):
            print(f"  - {w}")

        print("\nTOOLS:")
        for t in output.get("tools", []):
            print(f"  - {t}")

        print("\nSOURCES (snippets):")
        for i, s in enumerate(output.get("sources", []), 1):
            text = s.get("text", "")[:200].replace("\n", " ")
            print(f"  {i}. {text}...")

        print("\nSCORES:")
        print("  has_sources        :", score_has_sources(datum["expected"], output))
        print("  has_warnings_field :", score_has_warnings_field(datum["expected"], output))
        print("  has_tools_field    :", score_has_tools_field(datum["expected"], output))
        print("  keyword_in_sources :", score_keyword_in_sources(datum["expected"], output))
        print("  no_context_mixing  :", score_no_context_mixing(datum["expected"], output))
        print("  min_steps          :", score_min_steps(datum["expected"], output))

        print("=" * 80)
