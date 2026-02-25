"""Build a graph model from an Azure resource inventory."""
from typing import List

from tools.azdisc.util import normalize_id, slug, parent_id


def _safe_get(obj, *keys):
    """Safely traverse nested dicts/lists returning None if any key is missing."""
    cur = obj
    for key in keys:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list):
            # When key is int index
            try:
                cur = cur[key]
            except (IndexError, TypeError):
                return None
        else:
            return None
    return cur


def _iter_list(obj, *keys):
    """Safely get a list value; yields nothing if missing/None."""
    val = _safe_get(obj, *keys)
    if isinstance(val, list):
        yield from val


def _make_node(resource, is_external=False):
    return {
        "id": normalize_id(resource["id"]),
        "name": resource.get("name", ""),
        "type": normalize_id(resource.get("type", "")),
        "location": resource.get("location", ""),
        "resourceGroup": resource.get("resourceGroup", ""),
        "subscriptionId": resource.get("subscriptionId", ""),
        "isExternal": is_external,
    }


def build_graph(inventory: List[dict], rbac: List[dict]) -> dict:
    """Build graph {nodes, edges} from resource inventory and RBAC list."""
    node_map = {}  # normalized id -> node dict
    edges = []  # list of (src, dst, kind)

    # Index all inventory resources
    for resource in inventory:
        nid = normalize_id(resource["id"])
        node_map[nid] = _make_node(resource)

    def ensure_external(arm_id):
        """Add a placeholder external node if the id is not already in node_map."""
        nid = normalize_id(arm_id)
        if nid and nid not in node_map:
            node_map[nid] = {
                "id": nid,
                "name": nid.split("/")[-1],
                "type": "",
                "location": "",
                "resourceGroup": "",
                "subscriptionId": "",
                "isExternal": True,
            }
        return nid

    def add_edge(src_id, dst_id, kind="dependency"):
        if src_id and dst_id and src_id != dst_id:
            edges.append((normalize_id(src_id), normalize_id(dst_id), kind))

    for resource in inventory:
        rid = normalize_id(resource["id"])
        rtype = normalize_id(resource.get("type", ""))
        props = resource.get("properties") or {}

        # VM -> NIC
        if rtype == "microsoft.compute/virtualmachines":
            for nic_ref in _iter_list(props, "networkProfile", "networkInterfaces"):
                nic_id = nic_ref.get("id") if isinstance(nic_ref, dict) else None
                if nic_id:
                    ensure_external(nic_id)
                    add_edge(rid, nic_id)

            # VM -> OS managed disk
            os_disk_id = _safe_get(props, "storageProfile", "osDisk", "managedDisk", "id")
            if os_disk_id:
                ensure_external(os_disk_id)
                add_edge(rid, os_disk_id)

            # VM -> data managed disks
            for data_disk in _iter_list(props, "storageProfile", "dataDisks"):
                dd_id = _safe_get(data_disk, "managedDisk", "id")
                if dd_id:
                    ensure_external(dd_id)
                    add_edge(rid, dd_id)

        # NIC -> Subnet, NSG
        elif rtype == "microsoft.network/networkinterfaces":
            for ip_cfg in _iter_list(props, "ipConfigurations"):
                subnet_id = _safe_get(ip_cfg, "properties", "subnet", "id")
                if subnet_id:
                    ensure_external(subnet_id)
                    add_edge(rid, subnet_id)

            nsg_id = _safe_get(props, "networkSecurityGroup", "id")
            if nsg_id:
                ensure_external(nsg_id)
                add_edge(rid, nsg_id)

        # Subnet -> VNet, NSG, UDR
        elif rtype == "microsoft.network/virtualnetworks/subnets":
            vnet_id = parent_id(rid, "subnets")
            if vnet_id:
                ensure_external(vnet_id)
                add_edge(rid, vnet_id)

            nsg_id = _safe_get(props, "networkSecurityGroup", "id")
            if nsg_id:
                ensure_external(nsg_id)
                add_edge(rid, nsg_id)

            udr_id = _safe_get(props, "routeTable", "id")
            if udr_id:
                ensure_external(udr_id)
                add_edge(rid, udr_id)

        # VNet -> peered VNets
        elif rtype == "microsoft.network/virtualnetworks":
            for peering in _iter_list(props, "virtualNetworkPeerings"):
                peer_id = _safe_get(peering, "properties", "remoteVirtualNetwork", "id")
                if peer_id:
                    ensure_external(peer_id)
                    add_edge(rid, peer_id)

            # Also handle subnets embedded in VNet properties
            for subnet in _iter_list(props, "subnets"):
                subnet_id = subnet.get("id") if isinstance(subnet, dict) else None
                if not subnet_id:
                    continue
                snid = normalize_id(subnet_id)
                # Ensure subnet node exists with its properties
                if snid not in node_map:
                    node_map[snid] = {
                        "id": snid,
                        "name": subnet.get("name", snid.split("/")[-1]),
                        "type": "microsoft.network/virtualnetworks/subnets",
                        "location": resource.get("location", ""),
                        "resourceGroup": resource.get("resourceGroup", ""),
                        "subscriptionId": resource.get("subscriptionId", ""),
                        "isExternal": False,
                    }
                sub_props = subnet.get("properties") or {}
                # Subnet -> VNet
                add_edge(snid, rid)
                # Subnet -> NSG
                sub_nsg_id = _safe_get(sub_props, "networkSecurityGroup", "id")
                if sub_nsg_id:
                    ensure_external(sub_nsg_id)
                    add_edge(snid, sub_nsg_id)
                # Subnet -> UDR
                sub_udr_id = _safe_get(sub_props, "routeTable", "id")
                if sub_udr_id:
                    ensure_external(sub_udr_id)
                    add_edge(snid, sub_udr_id)

        # Private Endpoint -> subnet, target
        elif rtype == "microsoft.network/privateendpoints":
            pe_subnet_id = _safe_get(props, "subnet", "id")
            if pe_subnet_id:
                ensure_external(pe_subnet_id)
                add_edge(rid, pe_subnet_id)

            for conn in _iter_list(props, "privateLinkServiceConnections"):
                target_id = _safe_get(conn, "properties", "privateLinkServiceId")
                if target_id:
                    ensure_external(target_id)
                    add_edge(rid, target_id)

        # Public IP -> attachment
        elif rtype == "microsoft.network/publicipaddresses":
            ip_cfg_id = _safe_get(props, "ipConfiguration", "id")
            if ip_cfg_id:
                # Strip last two path segments to get parent resource
                parts = ip_cfg_id.rstrip("/").split("/")
                if len(parts) >= 3:
                    parent = "/".join(parts[:-2])
                    ensure_external(parent)
                    add_edge(rid, parent)

        # Load Balancer -> NIC backends
        elif rtype == "microsoft.network/loadbalancers":
            for pool in _iter_list(props, "backendAddressPools"):
                for ip_cfg_ref in _iter_list(
                    pool.get("properties") or {}, "backendIPConfigurations"
                ):
                    ip_cfg_id = ip_cfg_ref.get("id") if isinstance(ip_cfg_ref, dict) else None
                    if ip_cfg_id:
                        # Strip last two segments -> NIC id
                        parts = ip_cfg_id.rstrip("/").split("/")
                        if len(parts) >= 3:
                            nic_parent = "/".join(parts[:-2])
                            ensure_external(nic_parent)
                            add_edge(rid, nic_parent)

    # RBAC edges
    for ra in rbac:
        ra_id = normalize_id(ra["id"])
        if ra_id not in node_map:
            node_map[ra_id] = _make_node(ra)
        scope = normalize_id(
            str(_safe_get(ra, "properties", "scope") or "")
        )
        if scope:
            ensure_external(scope)
            add_edge(scope, ra_id, kind="rbac_assignment")

    # Deduplicate edges
    edge_set = set(edges)

    nodes = sorted(node_map.values(), key=lambda n: n["id"])
    sorted_edges = sorted(
        [{"src": s, "dst": d, "kind": k} for s, d, k in edge_set],
        key=lambda e: (e["src"], e["dst"], e["kind"]),
    )

    return {"nodes": nodes, "edges": sorted_edges}
