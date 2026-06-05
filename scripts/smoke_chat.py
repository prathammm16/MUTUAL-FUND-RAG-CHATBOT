#!/usr/bin/env python3

"""Phase 5 manual smoke — run RAG backend on golden queries (no HTTP server)."""



from __future__ import annotations



import argparse

import sys

from pathlib import Path



_ROOT = Path(__file__).resolve().parents[1]

if str(_ROOT) not in sys.path:

    sys.path.insert(0, str(_ROOT))



from app.rag.backend import ResponseType, run_rag  # noqa: E402



SMOKE_CASES: list[tuple[str, ResponseType, str]] = [

    ("What is the exit load on HDFC Gold ETF Fund of Fund?", ResponseType.ANSWER, "gold exit load"),

    ("Min SIP for silver fund?", ResponseType.ANSWER, "silver min SIP"),

    ("Which fund is better?", ResponseType.REFUSAL, "advisory refusal"),

    ("Compare 3Y returns", ResponseType.REFUSAL, "performance refusal"),

]





def _safe_console(text: str) -> str:

    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"

    return text.encode(encoding, errors="replace").decode(encoding)





def main(argv: list[str] | None = None) -> int:

    parser = argparse.ArgumentParser(description="Smoke-test Phase 5 RAG backend")

    parser.add_argument(

        "--store",

        default=str(_ROOT / "vector_store"),

        help="Chroma persist directory",

    )

    parser.add_argument(

        "--template",

        action="store_true",

        help="Force template generation (no Groq API call)",

    )

    args = parser.parse_args(argv)



    failed = 0

    for message, expected, label in SMOKE_CASES:

        result = run_rag(

            message,

            force_template=args.template,

            persist_directory=args.store,

        )

        ok = result.type == expected

        status = "OK" if ok else "FAIL"

        print(f"[{status}] {label}: type={result.type.value} (expected {expected.value})")

        if not ok:

            failed += 1

            continue

        preview = _safe_console(result.answer[:120].replace("\n", " "))

        print(f"       {preview}...")

        if result.citation_url:

            print(f"       citation: {result.citation_url}")



    if failed:

        print(f"\n{failed} case(s) failed")

        return 1

    print("\nAll smoke cases passed")

    return 0





if __name__ == "__main__":

    raise SystemExit(main())


