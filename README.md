# azure-to-plantuml

Deterministic, auditable **Azure Application Discovery → Azure-PlantUML** generator.

Discovers all Azure resources in one or more seed Resource Groups (plus their transitive
dependencies), builds a normalized graph, and emits an [Azure-PlantUML](https://github.com/plantuml-stdlib/Azure-PlantUML)
architecture diagram-as-code alongside Markdown catalog and edge reports.

---

## Prerequisites

| Tool | Minimum version | Notes |
|------|----------------|-------|
| Python | 3.9+ | stdlib only — no pip installs |
| Azure CLI (`az`) | 2.40+ | `az login` or service-principal env vars |
| `az graph` extension | any | `az extension add --name resource-graph` |
| Java | 11+ | Required only for `render` step |
| PlantUML jar | any recent | Set via `--plantuml-jar` or `PLANTUML_JAR` env var |
| Azure-PlantUML dist | any | Place under `vendor/azure-plantuml/dist/` |

> **WSL note:** all commands run natively in a WSL (Linux) shell on Azure Virtual Desktop.

---

## Quick Start

### 1. Authenticate to Azure

```bash
az login
# or for a service principal:
export AZURE_CLIENT_ID=...
export AZURE_CLIENT_SECRET=...
export AZURE_TENANT_ID=...
az login --service-principal -u $AZURE_CLIENT_ID -p $AZURE_CLIENT_SECRET --tenant $AZURE_TENANT_ID
```

### 2. Install the resource-graph extension (once)

```bash
az extension add --name resource-graph
```

### 3. Create an app config

Copy and edit the example:

```bash
cp -r app/example app/myapp
# Edit app/myapp/config.json
```

`app/myapp/config.json` schema:

```json
{
  "app": "myapp",
  "subscriptions": ["<subscription-guid>", ...],
  "seedResourceGroups": ["rg-prod", "rg-shared"],
  "outputDir": "app/myapp/out",
  "includeRbac": false
}
```

### 4. Run the full pipeline

```bash
python3 -m tools.azdisc run app/myapp/config.json
```

Or run individual steps:

```bash
python3 -m tools.azdisc discover  app/myapp/config.json   # → seed.json
python3 -m tools.azdisc expand    app/myapp/config.json   # → inventory.json, unresolved.json
python3 -m tools.azdisc graph     app/myapp/config.json   # → graph.json
python3 -m tools.azdisc puml      app/myapp/config.json   # → diagram.puml
python3 -m tools.azdisc render    app/myapp/config.json   # → diagram.svg
python3 -m tools.azdisc docs      app/myapp/config.json   # → catalog.md, edges.md
```

#### Render with a specific PlantUML jar

```bash
python3 -m tools.azdisc render app/myapp/config.json --plantuml-jar /opt/plantuml.jar
# or
export PLANTUML_JAR=/opt/plantuml.jar
python3 -m tools.azdisc run app/myapp/config.json
```

---

## Output Artifacts

All files are written to `outputDir` (defined in config).

| File | Description |
|------|-------------|
| `seed.json` | Unfiltered ARG query result for seed Resource Groups |
| `inventory.json` | Seed + all transitively discovered resources |
| `unresolved.json` | ARM IDs referenced in properties but not resolvable via ARG |
| `rbac.json` | Role assignments (only when `includeRbac: true`) |
| `graph.json` | Normalized nodes + edges |
| `diagram.puml` | Azure-PlantUML source (clustered REGION > RG > TYPE) |
| `diagram.svg` | Rendered diagram SVG |
| `catalog.md` | Resource counts by type / region / RG / subscription |
| `edges.md` | Edge counts by kind; top nodes by degree; unresolved summary |

### Invariants

- All ARM IDs are normalized to **lowercase** throughout.
- JSON output uses `indent=2, sort_keys=True` for deterministic diffs.
- Re-running against an unchanged Azure state produces **byte-identical** output files.
- Transitive expansion converges (max 50 iterations, chunk size 200 IDs).

---

## Repository Layout

```
tools/azdisc/
    __main__.py    CLI entry point
    config.py      AppConfig dataclass + loader
    arg.py         Azure Resource Graph wrapper (az graph query)
    expand.py      Transitive inventory expansion
    graph.py       Graph model (nodes + edges)
    emit_puml.py   PlantUML diagram emission
    render.py      PlantUML rendering (SVG)
    docs.py        Markdown catalog and edges report
    util.py        Shared utilities
    tests/
        fixtures/  Sample JSON fixtures for unit tests
        test_util.py
        test_graph.py
vendor/
    azure-plantuml/dist/   Azure-PlantUML library (provided by user)
app/
    example/
        config.json        Example configuration
        out/               Generated artifacts (git-ignored)
```

---

## Troubleshooting

### Auth / permissions

```
Error: az graph query failed
```

- Run `az account show` to verify you are logged in.
- Confirm the account has **Reader** role on all subscriptions listed in config.
- For resource graph, the account needs `Microsoft.ResourceGraph/resources/read` permission.

### Query limits

- ARG limits queries to 1000 results per page — the tool paginates automatically.
- Subscription chunks are capped at 20 per `az graph query` call.
- ID chunks are capped at 200 per lookup query.
- If you still hit throttling, reduce `chunk` sizes in `arg.py`.

### `az extension add --name resource-graph`

If `az graph` commands fail with "command not found", install the extension:

```bash
az extension add --name resource-graph
az extension update --name resource-graph
```

### PlantUML rendering fails

- Check `PLANTUML_JAR` is set or pass `--plantuml-jar`.
- Ensure `java` is on `$PATH`: `java -version`.
- The `vendor/azure-plantuml/dist/` directory must exist and contain `AzureCommon.puml`.

### Unresolved ARM IDs

Check `unresolved.json`. Common causes:

- Resource lives in a subscription not listed in `subscriptions`.
- Resource has been deleted but its ID still appears in a property.
- The ID is a logical scope string (e.g. a management group), not a trackable resource.

---

## Running Tests

```bash
python3 -m pytest tools/azdisc/tests/ -v
```

All tests use only stdlib and pytest — no Azure credentials required.
