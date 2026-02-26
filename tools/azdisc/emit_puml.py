"""Emit PlantUML diagram from graph model."""
import os
from collections import defaultdict

from tools.azdisc.util import slug

TYPE_MAP = {
    "microsoft.compute/virtualmachines": "AzureVirtualMachine",
    "microsoft.compute/disks": "AzureManagedDisks",
    "microsoft.network/virtualnetworks": "AzureVirtualNetwork",
    "microsoft.network/networkinterfaces": "AzureNetworkInterface",
    "microsoft.network/networksecuritygroups": "AzureNetworkSecurityGroup",
    "microsoft.network/publicipaddresses": "AzurePublicIPAddress",
    "microsoft.network/loadbalancers": "AzureLoadBalancer",
    "microsoft.network/routetables": "AzureRouteTable",
    "microsoft.network/privateendpoints": "AzurePrivateEndpoint",
    "microsoft.storage/storageaccounts": "AzureStorageAccount",
    "microsoft.web/sites": "AzureAppService",
    "microsoft.keyvault/vaults": "AzureKeyVault",
    "microsoft.sql/servers": "AzureSQLServer",
    "microsoft.sql/servers/databases": "AzureSQLDatabase",
    "microsoft.authorization/roleassignments": "AzureRoleAssignment",
    "microsoft.network/virtualnetworks/subnets": "AzureVirtualNetwork",
}

HEADER = """\
@startuml
!define AzurePuml ./vendor/azure-plantuml/dist
!include AzurePuml/AzureCommon.puml
!include AzurePuml/Compute/all.puml
!include AzurePuml/Network/all.puml
!include AzurePuml/Storage/all.puml
!include AzurePuml/Web/all.puml
!include AzurePuml/Integration/all.puml
!include AzurePuml/Security/all.puml
"""

FOOTER = "@enduml\n"


def _type_short(node_type: str) -> str:
    if not node_type:
        return "unknown"
    return node_type.split("/")[-1]


def emit(graph: dict, output_path: str):
    """Write a PlantUML .puml file from a graph dict."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Group nodes by (location, resourceGroup, typeShort)
    groups = defaultdict(list)
    for node in nodes:
        location = node.get("location") or "unknown"
        rg = node.get("resourceGroup") or "external"
        ts = _type_short(node.get("type", ""))
        groups[(location, rg, ts)].append(node)

    lines = [HEADER]

    # Render clusters
    for (location, rg, ts), group_nodes in sorted(groups.items()):
        loc_safe = location.replace('"', "'")
        rg_safe = rg.replace('"', "'")
        ts_safe = ts.replace('"', "'")
        lines.append(f'package "{loc_safe}" {{')
        lines.append(f'  package "{rg_safe}" {{')
        lines.append(f'    package "{ts_safe}" {{')
        for node in group_nodes:
            alias = slug(node["id"])
            name = node.get("name") or node["id"].split("/")[-1]
            name_safe = name.replace('"', "'")
            ntype = node.get("type", "")
            macro = TYPE_MAP.get(ntype)
            if macro:
                lines.append(f'      {macro}({alias}, "{name_safe}")')
            else:
                lines.append(f'      rectangle "{name_safe}\\n({ts_safe})" as {alias}')
        lines.append("    }")
        lines.append("  }")
        lines.append("}")
        lines.append("")

    # Render edges
    lines.append("' ---- edges ----")
    for edge in edges:
        src_alias = slug(edge["src"])
        dst_alias = slug(edge["dst"])
        lines.append(f"{src_alias} --> {dst_alias}")

    lines.append("")
    lines.append(FOOTER)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
