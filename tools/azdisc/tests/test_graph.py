"""Tests for tools.azdisc.graph."""
import json
import os
import pytest

from tools.azdisc.graph import build_graph
from tools.azdisc.util import normalize_id

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_resources():
    with open(os.path.join(FIXTURES_DIR, "sample_resources.json"), encoding="utf-8") as fh:
        return json.load(fh)


SUB = "00000000-0000-0000-0000-000000000001"
VM_ID = normalize_id(
    f"/subscriptions/{SUB}/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-test"
)
NIC_ID = normalize_id(
    f"/subscriptions/{SUB}/resourceGroups/rg-test/providers/Microsoft.Network/networkInterfaces/nic-test"
)
VNET_ID = normalize_id(
    f"/subscriptions/{SUB}/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-test"
)
SUBNET_ID = normalize_id(
    f"/subscriptions/{SUB}/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-test/subnets/subnet-default"
)
NSG_ID = normalize_id(
    f"/subscriptions/{SUB}/resourceGroups/rg-test/providers/Microsoft.Network/networkSecurityGroups/nsg-test"
)
DISK_ID = normalize_id(
    f"/subscriptions/{SUB}/resourceGroups/rg-test/providers/Microsoft.Compute/disks/disk-os"
)


@pytest.fixture
def graph():
    resources = load_resources()
    return build_graph(resources, [])


def test_build_graph_nodes(graph):
    node_ids = {n["id"] for n in graph["nodes"]}
    assert VM_ID in node_ids
    assert NIC_ID in node_ids
    assert VNET_ID in node_ids
    assert NSG_ID in node_ids
    assert DISK_ID in node_ids


def test_build_graph_vm_nic_edge(graph):
    edges = {(e["src"], e["dst"]) for e in graph["edges"]}
    assert (VM_ID, NIC_ID) in edges


def test_build_graph_nic_subnet_edge(graph):
    edges = {(e["src"], e["dst"]) for e in graph["edges"]}
    assert (NIC_ID, SUBNET_ID) in edges


def test_build_graph_subnet_vnet_edge(graph):
    edges = {(e["src"], e["dst"]) for e in graph["edges"]}
    assert (SUBNET_ID, VNET_ID) in edges


def test_build_graph_dedup_edges(graph):
    edge_tuples = [(e["src"], e["dst"], e["kind"]) for e in graph["edges"]]
    assert len(edge_tuples) == len(set(edge_tuples)), "Duplicate edges found"


def test_external_nodes_created(graph):
    """Nodes referenced in properties but not in inventory should appear as external."""
    # All referenced IDs should appear in nodes (either real or external)
    node_ids = {n["id"] for n in graph["nodes"]}
    for edge in graph["edges"]:
        assert edge["src"] in node_ids, f"src not in nodes: {edge['src']}"
        assert edge["dst"] in node_ids, f"dst not in nodes: {edge['dst']}"
