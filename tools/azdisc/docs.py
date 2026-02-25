"""Generate markdown documentation from inventory and graph data."""
import os
from collections import Counter
from typing import List


def write_catalog(inventory_data: dict, output_dir: str):
    """Write catalog.md with resource counts by type, region, RG, and subscription."""
    resources = inventory_data if isinstance(inventory_data, list) else inventory_data.get("resources", [])

    by_type = Counter()
    by_region = Counter()
    by_rg = Counter()
    by_sub = Counter()

    for r in resources:
        by_type[r.get("type", "(unknown)")] += 1
        by_region[r.get("location", "(unknown)")] += 1
        by_rg[r.get("resourceGroup", "(unknown)")] += 1
        by_sub[r.get("subscriptionId", "(unknown)")] += 1

    total = len(resources)
    lines = ["# Resource Catalog", ""]

    def _table(counter, label):
        rows = [""]
        rows.append(f"## By {label}")
        rows.append("")
        rows.append(f"| {label} | Count |")
        rows.append("|---|---|")
        for k, v in sorted(counter.items()):
            rows.append(f"| {k} | {v} |")
        rows.append(f"| **Total** | **{total}** |")
        return rows

    lines += _table(by_type, "Type")
    lines += _table(by_region, "Region")
    lines += _table(by_rg, "Resource Group")
    lines += _table(by_sub, "Subscription")
    lines.append("")

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "catalog.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def write_edges(graph: dict, unresolved: List[str], output_dir: str):
    """Write edges.md with edge counts, top nodes by degree, and unresolved IDs."""
    edges = graph.get("edges", [])
    nodes = graph.get("nodes", [])

    kind_counter = Counter(e["kind"] for e in edges)

    degree = Counter()
    for e in edges:
        degree[e["src"]] += 1
        degree[e["dst"]] += 1

    top_nodes = degree.most_common(20)

    lines = ["# Graph Edges Report", ""]

    lines.append("## Edge Counts by Kind")
    lines.append("")
    lines.append("| Kind | Count |")
    lines.append("|---|---|")
    for kind, cnt in sorted(kind_counter.items()):
        lines.append(f"| {kind} | {cnt} |")
    lines.append(f"| **Total** | **{len(edges)}** |")
    lines.append("")

    lines.append("## Top 20 Nodes by Degree")
    lines.append("")
    lines.append("| Node ID | Degree |")
    lines.append("|---|---|")
    for nid, deg in top_nodes:
        lines.append(f"| {nid} | {deg} |")
    lines.append("")

    lines.append(f"## Unresolved References ({len(unresolved)} total)")
    lines.append("")
    if unresolved:
        lines.append("First 20 samples:")
        lines.append("")
        for uid in sorted(unresolved)[:20]:
            lines.append(f"- {uid}")
    else:
        lines.append("_None_")
    lines.append("")

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "edges.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
