"""Score requirement extraction against hand-labelled gold requirements in ../samples/*/.

Usage (from backend/):  uv run python scripts/eval_extraction.py [--provider offline|anthropic]
A gold item counts as found when an extracted requirement matches it with similarity >= 0.85.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.llm.client import UsageMeter, get_llm
from app.pipeline.analyse import classify_chunks, extract_from_chunks
from app.pipeline.chunk import build_chunks
from app.pipeline.parse import parse_document
from app.pipeline.textutil import similarity

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
MATCH = 0.85


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["offline", "anthropic"], default=None)
    args = parser.parse_args()
    settings = get_settings()
    if args.provider:
        settings = settings.model_copy(update={"llm_provider": args.provider})
    llm = get_llm(settings)
    usage = UsageMeter(settings.llm_max_tokens_per_project)
    print(f"Provider: {llm.name}")
    for gold_file in sorted(SAMPLES.glob("*/gold_requirements.json")):
        rfp = gold_file.parent / "rfp.pdf"
        gold = [str(g["text"]) for g in json.loads(gold_file.read_text())]
        doc = parse_document(rfp, "pdf")
        chunks = build_chunks(doc)
        classify_chunks(llm, chunks, usage)
        pages = {p.page: p.text for p in doc.pages}
        found = [i.text for i in extract_from_chunks(llm, settings, chunks, pages, usage)]
        hits = [g for g in gold if any(similarity(g, f) >= MATCH for f in found)]
        true_positive = [f for f in found if any(similarity(g, f) >= MATCH for g in gold)]
        recall = len(hits) / len(gold) if gold else 0.0
        precision = len(true_positive) / len(found) if found else 0.0
        print(
            f"{gold_file.parent.name}: recall {recall:.0%} ({len(hits)}/{len(gold)}), precision {precision:.0%} ({len(true_positive)}/{len(found)})"
        )
        for missed in sorted(set(gold) - set(hits)):
            print(f"  missed: {missed}")
    print(f"Tokens used: {usage.used:,}")


if __name__ == "__main__":
    main()
