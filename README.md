# dc_qdxml_validator

Teamcenter Quick Deploy XML Connection Validation & Report Tool

Validates `<connectedTo>` relationships in TC Quick Deploy XML files against 11 architecture rules, then generates per-component HTML reports. **Fully dynamic** — no hardcoded hostnames, no external mapping files, no re-packaging needed when servers change.

## Features

- **11 validation rules** covering full-mesh, odd/even pairing, 1:1 mapping, and full-connection checks
- **Dynamic discovery**: Clusters, roles, and hostnames are all inferred from XML content — zero hardcoded names
- **Per-component reports**: 30+ HTML reports with connection details, property patterns, and cross-reference
- **Auto-detect XML**: Double-click the exe to find and validate the XML in the same directory
- **Config-aware titles**: Reports use the XML's `<configName>` as header
- **Zero external dependencies**: No mapping files, no config files — just the exe and the XML

## Validation Rules

| Rule | Type | Source → Target | Description |
|------|------|-----------------|-------------|
| R1 | Full-mesh | Web Tier → Server Manager | Each WT connects to all SMs in the same cluster |
| R2 | Odd/Even 1:1 | Gateway → VIS Pool Assigner | Odd-numbered GW → VIS[0], Even → VIS[1] |
| R3 | 1:1 | BL-Dispatcher → Web | DISP BL connects to Web |
| R4 | 1:1 | BL-DC → Web | DC BL connects to Web |
| R5 | 1:1 | 4tier Client → Web | 4-tier rich client connects to a Web |
| R6 | 1:1 | FTS Indexer → Web | Indexer connects to a Web |
| R7 | 1:1 | VIS Pool Assigner → Web | VIS pool connects to a Web |
| R8 | Same-host | Gateway → Web | Gateway must connect to its own Web (same machine) |
| R9 | Full-connection | Special components | Console, MSF, Dispatcher, Gateway, VIS, FSC all have full-connection checks |
| R10 | FSC Master/Non-Master | FSC → FSC | Master FSC → all FSCs; Non-Master → Master FSCs only |
| R11 | Sequential | connectedTo | Same-type connectedTo entries must be sequential within a component |

## Dynamic Discovery

All validation is driven by XML content — no hardcoded hostnames or cluster definitions:

- **Clusters**: Built from `fnd0_serverManagerDisplayClusterId` on SM components
- **APP numbering**: Extracted from machineName via regex (works with any prefix like `APP01` or `jttcapp01`)
- **DISP identification**: Machines with `fnd0_dispatcherModule` component
- **DC identification**: BL servers not on SM or DISP machines
- **Corporate server**: Detected via `fnd0_corporateserver` component
- **FSC Master/Cache**: Detected via `fnd0_isMaster` property
- **Full-connection components**: Found dynamically by component ID

## Usage

### Standalone EXE

```bash
# Double-click to auto-detect XML and run all checks + generate reports
dc_qdxml_validator.exe

# Specify XML path
dc_qdxml_validator.exe path/to/config.xml

# Run checks only (no reports)
dc_qdxml_validator.exe config.xml --check

# Generate report for a specific component
dc_qdxml_validator.exe config.xml --report fnd0_fsc

# Generate all reports
dc_qdxml_validator.exe config.xml --all
```

### Python Script

```bash
python dc_qdxml_validator.py config.xml
```

### Output

Check results print to console. Reports are generated in `./validator/` subdirectory:

| File | Description |
|------|-------------|
| `validator/index.html` | Report index page |
| `validator/report_<cid>.html` | Per-component detail report |
| `validator/validator_style.css` | Shared report stylesheet |

## Component Count Standards

For 56 APP servers:

| Component | Count |
|-----------|-------|
| fnd0_j2ee_tcwebtier | 56 |
| fnd0_serverManager | 56 |
| fnd0_blserver | 58 (55 APP + DC01 + DISP01 + DISP02) |
| fnd0_fsc | 86 (9 Master + 55 co-located + 22 cache) |
| fnd0_corporateserver | 1 |
| fnd0_2tierrichclient | 13 |
| aws2_client_gateway_webtier | 6 |
| fnd0_tccs | 17 |

## Building the EXE

Requires Python 3.13+ and PyInstaller:

```bash
pip install pyinstaller lxml
pyinstaller --onefile --distpath output --workpath build dc_qdxml_validator.py
```

Output: `output/dc_qdxml_validator.exe` (~13MB)

## File Structure

```
dc_qdxml_validator/
├── dc_qdxml_validator.py    # Main script (single file, all-in-one)
├── output/
│   └── dc_qdxml_validator.exe
└── README.md
```

## Related Projects

- **[dc_qdxml_to_arch](https://github.com/fei7yang/dc_qdxml_to_arch)** — TC Quick Deploy XML → Architecture Visualization Tool
- **[dc_qdxml_replace](https://github.com/fei7yang/dc_qdxml_replace)** — Hostname replacement tool for TC Quick Deploy XML

## License

Internal tool — for Teamcenter deployment validation.
