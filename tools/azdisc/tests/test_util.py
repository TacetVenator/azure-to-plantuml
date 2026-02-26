"""Tests for tools.azdisc.util."""
import re
import pytest

from tools.azdisc.util import (
    extract_arm_ids,
    normalize_id,
    slug,
    chunk,
    parent_id,
)

SUB = "00000000-0000-0000-0000-000000000001"
NIC_ID = f"/subscriptions/{SUB}/resourceGroups/rg-test/providers/Microsoft.Network/networkInterfaces/nic-test"
VNET_ID = f"/subscriptions/{SUB}/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-test"
SUBNET_ID = f"{VNET_ID}/subnets/subnet-default"


def test_extract_arm_ids_nested():
    obj = {
        "a": {
            "b": NIC_ID,
            "c": "not-an-arm-id",
        }
    }
    result = extract_arm_ids(obj)
    assert NIC_ID.lower() in result
    assert "not-an-arm-id" not in result


def test_extract_arm_ids_list():
    obj = [NIC_ID, VNET_ID, "random-string", 42]
    result = extract_arm_ids(obj)
    assert NIC_ID.lower() in result
    assert VNET_ID.lower() in result
    assert len([x for x in result if "random" in x]) == 0


def test_normalize_id():
    assert normalize_id("  /Subscriptions/ABC  ") == "/subscriptions/abc"
    assert normalize_id("/subscriptions/abc") == "/subscriptions/abc"


def test_slug_deterministic():
    s1 = slug(NIC_ID)
    s2 = slug(NIC_ID)
    assert s1 == s2


def test_slug_safe_chars():
    s = slug(NIC_ID)
    assert re.match(r'^[a-z0-9_]+$', s), f"Unsafe chars in slug: {s!r}"
    assert len(s) <= 60


def test_chunk():
    lst = list(range(10))
    chunks = list(chunk(lst, 3))
    assert chunks == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]


def test_chunk_exact():
    lst = list(range(6))
    chunks = list(chunk(lst, 3))
    assert chunks == [[0, 1, 2], [3, 4, 5]]


def test_parent_id_subnets():
    result = parent_id(SUBNET_ID, "subnets")
    assert result.lower() == VNET_ID.lower()


def test_parent_id_missing_segment():
    result = parent_id(VNET_ID, "subnets")
    assert result == VNET_ID
