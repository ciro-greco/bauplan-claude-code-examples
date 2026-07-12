"""
Emit a Markdown summary of the conversion pipeline's output for a PR comment.

Reads `bauplan.segment_conversion` (and the source row count) from the given Bauplan
ref and prints a Markdown table to stdout. Uses only the bauplan SDK (+ its bundled
pyarrow) — no pandas/polars needed.

Usage:
    python conversion-pipeline/ci/summarize.py <bauplan_ref>
"""

import sys

import bauplan

# High value -> low value ordering for the report.
ORDER = {"high": 0, "medium": 1, "low": 2}


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: summarize.py <bauplan_ref>")
    ref = sys.argv[1]

    client = bauplan.Client()

    rows = client.query(
        "SELECT customer_segment, total_sessions, "
        "CAST(converting_sessions AS BIGINT) AS converting_sessions, conversion_rate "
        "FROM bauplan.segment_conversion",
        ref=ref,
    ).to_pylist()
    rows.sort(key=lambda r: ORDER.get(r["customer_segment"], 99))

    total = sum(r["total_sessions"] for r in rows)
    converting = sum(r["converting_sessions"] for r in rows)
    overall = converting / total if total else 0.0

    source_rows = client.query(
        "SELECT COUNT(*) AS n FROM bauplan.ecommerce_sessions_week", ref=ref
    ).to_pylist()[0]["n"]

    out = [
        "### 📊 Data summary — session → purchase conversion",
        "",
        f"Source `bauplan.ecommerce_sessions_week` — **{source_rows:,} rows** · "
        f"data branch `{ref}`",
        "",
        "| Segment | Sessions | Converting | Conversion |",
        "|---|--:|--:|--:|",
    ]
    for r in rows:
        out.append(
            f"| {r['customer_segment'].capitalize()} "
            f"| {r['total_sessions']:,} "
            f"| {r['converting_sessions']:,} "
            f"| {r['conversion_rate'] * 100:.2f}% |"
        )
    out.append(f"| **Overall** | **{total:,}** | **{converting:,}** | **{overall * 100:.2f}%** |")

    print("\n".join(out))


if __name__ == "__main__":
    main()
