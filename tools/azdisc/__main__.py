"""CLI entry point for azdisc tool."""
import argparse
import json
import os
import sys

from tools.azdisc.config import load_config
from tools.azdisc.arg import AzureResourceGraph, AzDiscError
from tools.azdisc.expand import expand, build_rbac_scopes
from tools.azdisc.graph import build_graph
from tools.azdisc.emit_puml import emit
from tools.azdisc.render import render as render_puml
from tools.azdisc.docs import write_catalog, write_edges
from tools.azdisc.util import sort_keys


def _write_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sort_keys(data), fh, indent=2, sort_keys=True)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def cmd_discover(config, out_dir):
    print("  [discover] running seed query...", file=sys.stderr)
    arg = AzureResourceGraph(config.subscriptions)
    seed = arg.query_seed(config.seedResourceGroups)
    _write_json(os.path.join(out_dir, "seed.json"), seed)
    print(f"  [discover] {len(seed)} resources written to seed.json", file=sys.stderr)
    return seed


def cmd_expand(config, out_dir, seed=None):
    print("  [expand] expanding inventory...", file=sys.stderr)
    arg = AzureResourceGraph(config.subscriptions)

    # Use existing seed if available
    seed_path = os.path.join(out_dir, "seed.json")
    if seed is None and os.path.exists(seed_path):
        print("  [expand] loading existing seed.json", file=sys.stderr)
        seed = _read_json(seed_path)

    inventory, unresolved = expand(config, arg)

    if config.includeRbac:
        print("  [expand] querying RBAC...", file=sys.stderr)
        scopes = build_rbac_scopes(inventory)
        rbac = arg.query_rbac(scopes)
    else:
        rbac = []

    _write_json(os.path.join(out_dir, "inventory.json"), inventory)
    _write_json(os.path.join(out_dir, "unresolved.json"), unresolved)
    _write_json(os.path.join(out_dir, "rbac.json"), rbac)
    print(
        f"  [expand] {len(inventory)} resources, {len(unresolved)} unresolved",
        file=sys.stderr,
    )
    return inventory, unresolved, rbac


def cmd_graph(out_dir):
    print("  [graph] building graph...", file=sys.stderr)
    inventory = _read_json(os.path.join(out_dir, "inventory.json"))
    rbac_path = os.path.join(out_dir, "rbac.json")
    rbac = _read_json(rbac_path) if os.path.exists(rbac_path) else []
    graph = build_graph(inventory, rbac)
    _write_json(os.path.join(out_dir, "graph.json"), graph)
    print(
        f"  [graph] {len(graph['nodes'])} nodes, {len(graph['edges'])} edges",
        file=sys.stderr,
    )
    return graph


def cmd_puml(out_dir):
    print("  [puml] generating PlantUML...", file=sys.stderr)
    graph = _read_json(os.path.join(out_dir, "graph.json"))
    puml_path = os.path.join(out_dir, "diagram.puml")
    emit(graph, puml_path)
    print(f"  [puml] written to {puml_path}", file=sys.stderr)
    return puml_path


def cmd_render(out_dir, plantuml_jar=None):
    print("  [render] rendering SVG...", file=sys.stderr)
    puml_path = os.path.join(out_dir, "diagram.puml")
    svg_path = render_puml(puml_path, out_dir, plantuml_jar=plantuml_jar)
    print(f"  [render] written to {svg_path}", file=sys.stderr)
    return svg_path


def cmd_docs(out_dir):
    print("  [docs] generating docs...", file=sys.stderr)
    inventory = _read_json(os.path.join(out_dir, "inventory.json"))
    graph = _read_json(os.path.join(out_dir, "graph.json"))
    unresolved_path = os.path.join(out_dir, "unresolved.json")
    unresolved = _read_json(unresolved_path) if os.path.exists(unresolved_path) else []
    write_catalog(inventory, out_dir)
    write_edges(graph, unresolved, out_dir)
    print("  [docs] catalog.md and edges.md written", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.azdisc",
        description="Azure resource discovery and diagram tool",
    )
    parser.add_argument(
        "command",
        choices=["run", "discover", "expand", "graph", "puml", "render", "docs"],
        help="Command to execute",
    )
    parser.add_argument("config_path", help="Path to JSON config file")
    parser.add_argument("--plantuml-jar", default=None, help="Path to plantuml.jar")
    args = parser.parse_args()

    try:
        config = load_config(args.config_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        sys.exit(1)

    out_dir = config.outputDir
    os.makedirs(out_dir, exist_ok=True)
    print(f"Output directory: {out_dir}", file=sys.stderr)

    try:
        if args.command == "discover":
            cmd_discover(config, out_dir)

        elif args.command == "expand":
            cmd_expand(config, out_dir)

        elif args.command == "graph":
            cmd_graph(out_dir)

        elif args.command == "puml":
            cmd_puml(out_dir)

        elif args.command == "render":
            cmd_render(out_dir, plantuml_jar=args.plantuml_jar)

        elif args.command == "docs":
            cmd_docs(out_dir)

        elif args.command == "run":
            cmd_discover(config, out_dir)
            cmd_expand(config, out_dir)
            cmd_graph(out_dir)
            cmd_puml(out_dir)
            cmd_render(out_dir, plantuml_jar=args.plantuml_jar)
            cmd_docs(out_dir)

    except AzDiscError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if exc.cmd:
            print(f"Command: {exc.cmd}", file=sys.stderr)
        if exc.stderr:
            print(f"Stderr: {exc.stderr}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
