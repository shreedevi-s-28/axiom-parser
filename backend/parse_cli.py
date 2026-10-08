#!/usr/bin/env python3
"""CLI entry point for AxiomParse universal parser.

Usage:
  python parse_cli.py input.pdf --out ./out_dir
  python parse_cli.py document.docx -o results/
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Make app importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.pipeline import UniversalIngestionPipeline
from app.core.errors import PipelineError


def main():
    parser = argparse.ArgumentParser(description="AxiomParse universal document parser")
    parser.add_argument("input", help="Path to input file")
    parser.add_argument("--out", "-o", default="./parse_output", help="Output directory")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    inp = Path(args.input)
    if not inp.is_file():
        print(json.dumps({"status": "error", "error": {"code": "FILE_NOT_FOUND", "message": str(inp)}}))
        sys.exit(1)

    content = inp.read_bytes()
    if len(content) == 0:
        print(json.dumps({"status": "error", "error": {"code": "EMPTY_FILE", "message": "File is empty"}}))
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    pipeline = UniversalIngestionPipeline()
    try:
        result = asyncio.run(pipeline.execute(inp.name, content, "application/octet-stream"))
    except PipelineError as e:
        err = {
            "status": "error",
            "error": {
                "code": e.error_code,
                "message": e.detail,
                "recoverable": e.status_code < 500,
                "diagnostics": e.diagnostics,
            },
        }
        print(json.dumps(err, indent=2 if args.pretty else None))
        (out_dir / "error.json").write_text(json.dumps(err, indent=2))
        sys.exit(2)
    except Exception as exc:
        err = {
            "status": "error",
            "error": {
                "code": "PARSER_FAILURE",
                "message": str(exc),
                "recoverable": False,
            },
        }
        print(json.dumps(err, indent=2 if args.pretty else None))
        (out_dir / "error.json").write_text(json.dumps(err, indent=2))
        sys.exit(3)

    # Write outputs
    data = result.model_dump()
    data["status"] = "success"
    (out_dir / "document.json").write_text(
        json.dumps(data, indent=2 if args.pretty else None, default=str)
    )
    (out_dir / "document.md").write_text(result.markdown or "")
    print(f"Wrote {out_dir / 'document.json'} and {out_dir / 'document.md'}")
    print(f"Pages: {result.page_count}  Blocks: {len(result.blocks)}  Avg conf: {result.metrics.confidence_average}")


if __name__ == "__main__":
    main()
