"""
Emit a Markdown summary of a pipeline's result table for a PR comment.

Generic: reads the result table from the given Bauplan ref and renders every row as a
Markdown table. Driven by the pipeline manifest (.bauplan/pr.env) so it works for any
pipeline, not just the conversion demo. Uses only the bauplan SDK (+ bundled pyarrow).

Usage (args or env vars BAUPLAN_BRANCH / RESULT_TABLE):
    python scripts/summarize_pipeline.py <bauplan_ref> <result_table>
"""

import os
import sys
from decimal import Decimal

import bauplan


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.4f}"
    if isinstance(v, Decimal):
        v = int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def md_table(rows):
    if not rows:
        return "_(no rows)_"
    cols = list(rows[0].keys())
    lines = [
        "| " + " | ".join(cols) + " |",
        "|" + "|".join(["---"] * len(cols)) + "|",
    ]
    for r in rows:
        lines.append("| " + " | ".join(_fmt(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def main():
    branch = os.environ.get("BAUPLAN_BRANCH") or (sys.argv[1] if len(sys.argv) > 1 else None)
    table = os.environ.get("RESULT_TABLE") or (sys.argv[2] if len(sys.argv) > 2 else None)
    if not branch or not table:
        sys.exit("usage: summarize_pipeline.py <bauplan_ref> <result_table> "
                 "(or set BAUPLAN_BRANCH / RESULT_TABLE)")

    client = bauplan.Client()
    rows = client.query(f"SELECT * FROM {table}", ref=branch).to_pylist()

    print(f"### 📊 Result — `{table}`")
    print()
    print(f"Data branch `{branch}` · {len(rows)} rows")
    print()
    print(md_table(rows))


if __name__ == "__main__":
    main()
