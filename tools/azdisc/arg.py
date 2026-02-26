"""Azure Resource Graph query wrapper."""
import json
import subprocess
from typing import List

from tools.azdisc.util import chunk


class AzDiscError(Exception):
    """Raised when an az CLI call fails."""

    def __init__(self, message: str, cmd=None, stdout=None, stderr=None):
        super().__init__(message)
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr


class AzureResourceGraph:
    def __init__(self, subscriptions: List[str]):
        self.subscriptions = subscriptions

    def _run_query(self, kql: str, description: str) -> List[dict]:
        """Execute az graph query with pagination and chunked subscriptions (max 20 per call)."""
        results = []
        sub_chunks = list(chunk(self.subscriptions, 20))

        for subs in sub_chunks:
            skip_token = None
            while True:
                cmd = [
                    "az", "graph", "query",
                    "-q", kql,
                    "--subscriptions", *subs,
                    "--first", "1000",
                ]
                if skip_token:
                    cmd += ["--skip-token", skip_token]

                try:
                    proc = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                except FileNotFoundError as exc:
                    raise AzDiscError(
                        f"az CLI not found while running: {description}",
                        cmd=cmd,
                        stdout="",
                        stderr=str(exc),
                    ) from exc

                if proc.returncode != 0:
                    raise AzDiscError(
                        f"az graph query failed: {description}",
                        cmd=cmd,
                        stdout=proc.stdout,
                        stderr=proc.stderr,
                    )

                try:
                    data = json.loads(proc.stdout)
                except json.JSONDecodeError as exc:
                    raise AzDiscError(
                        f"Failed to parse az graph output: {description}",
                        cmd=cmd,
                        stdout=proc.stdout,
                        stderr=proc.stderr,
                    ) from exc

                page_results = data.get("data", [])
                results.extend(page_results)

                skip_token = data.get("skipToken") or data.get("skip_token")
                if not skip_token:
                    break

        return results

    def query_seed(self, seed_rgs: List[str]) -> List[dict]:
        """Query all resources in seed resource groups."""
        rg_list = ", ".join(f"'{rg}'" for rg in seed_rgs)
        kql = (
            f"resources | where resourceGroup in~ ({rg_list}) "
            "| project id, name, type, location, subscriptionId, resourceGroup, properties"
        )
        return self._run_query(kql, "seed query")

    def query_by_ids(self, ids: List[str]) -> List[dict]:
        """Fetch resources by ARM IDs in chunks of 200."""
        results = []
        for id_chunk in chunk(ids, 200):
            id_list = ", ".join(f"'{i}'" for i in id_chunk)
            kql = (
                f"resources | where id in~ ({id_list}) "
                "| project id, name, type, location, subscriptionId, resourceGroup, properties"
            )
            results.extend(self._run_query(kql, "query_by_ids"))
        return results

    def query_rbac(self, scopes: List[str]) -> List[dict]:
        """Query role assignments for given scopes."""
        scope_list = ", ".join(f"'{s}'" for s in scopes)
        kql = (
            "authorizationresources "
            "| where type =~ 'microsoft.authorization/roleassignments' "
            "| extend scope = tolower(tostring(properties.scope)) "
            f"| where scope in~ ({scope_list}) "
            "| project id, name, type, subscriptionId, resourceGroup, properties"
        )
        return self._run_query(kql, "rbac query")
