"""Expand resource inventory by following ARM ID references."""
from typing import List, Tuple

from tools.azdisc.config import AppConfig
from tools.azdisc.arg import AzureResourceGraph
from tools.azdisc.util import extract_arm_ids, normalize_id, chunk

MAX_ITERATIONS = 50


def expand(config: AppConfig, arg: AzureResourceGraph) -> Tuple[List[dict], List[str]]:
    """
    Starting from seed resource groups, expand inventory by following ARM ID references.

    Returns (inventory, unresolved) where unresolved is a list of ARM IDs that were
    referenced but could not be fetched.
    """
    # Seed query
    inventory = arg.query_seed(config.seedResourceGroups)
    collected_ids = {normalize_id(r["id"]) for r in inventory}
    unresolved = set()

    for _ in range(MAX_ITERATIONS):
        # Extract all ARM IDs referenced in current inventory
        all_referenced = set()
        for resource in inventory:
            all_referenced |= extract_arm_ids(resource)

        missing = all_referenced - collected_ids - unresolved
        if not missing:
            break

        fetched = arg.query_by_ids(list(missing))
        fetched_ids = {normalize_id(r["id"]) for r in fetched}

        # IDs that couldn't be resolved
        unresolved |= missing - fetched_ids

        inventory.extend(fetched)
        collected_ids |= fetched_ids

    return inventory, sorted(unresolved)


def build_rbac_scopes(resources: List[dict]) -> List[str]:
    """Return all resource IDs plus resource-group scope strings."""
    scopes = set()
    for r in resources:
        scopes.add(normalize_id(r["id"]))
        sub = r.get("subscriptionId", "")
        rg = r.get("resourceGroup", "")
        if sub and rg:
            rg_scope = f"/subscriptions/{sub}/resourcegroups/{rg}".lower()
            scopes.add(rg_scope)
    return sorted(scopes)
