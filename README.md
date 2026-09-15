# dc_qdxml_validator

Teamcenter Quick Deploy XML Connection Validation & Report Tool

Validates `<connectedTo>` relationships and structural sanity in TC Quick Deploy XML files, then generates per-component HTML reports. **Fully dynamic** — no hardcoded hostnames, no external mapping files, no re-packaging needed when servers change.

> 纯动态原则：所有规则从 XML 内容推断，新增/删除服务器后无需修改本工具。

## Features

- **20+ validation rules** covering full-mesh, odd/even pairing, 1:1 mapping, full-connection, dangling-reference, mesh-symmetry, and format sanity checks
- **Dynamic discovery**: Clusters, roles, and hostnames are all inferred from XML content — zero hardcoded names
- **Per-component reports**: 30+ HTML reports with connection details, property patterns, and cross-reference
- **Auto-detect XML**: Double-click the exe to find and validate the XML in the same directory
- **Config-aware titles**: Reports use the XML's `<configName>` as header
- **Zero external dependencies**: No mapping files, no config files — just the exe and the XML

## Validation Rules

| Rule | Type | Source → Target | Severity | Description |
|------|------|-----------------|----------|-------------|
| R1 | Full-mesh | Web Tier → Server Manager | ❌ | 每个 WT 连集群内全部 SM |
| R2 | Odd/Even 1:1 | Gateway → VIS Pool Assigner | ⚠️ | 奇数 GW→VIS[0]、偶数→VIS[1]（VIS 不足 2 个时跳过并警告） |
| R3 | 1:1 | BL-Dispatcher → Web | ⚠️ | DISP BL 连 Web（源 XML 中常为空，DC 导入时自动补，故仅警告） |
| R4 | 1:1 | BL-DC → Web | ⚠️ | DC BL 连 Web（同上，仅警告） |
| R5 | 1:1 | 4tier Client → Web | ❌ | 4-tier rich client 连 Web |
| R6 | 1:1 | FTS Indexer → Web | ❌ | Indexer 连 Web |
| R7 | 1:1 | VIS Pool Assigner → Web | ❌ | VIS pool 连 Web |
| R8 | Same-host | Gateway → Web | ❌ | Gateway 必须连本机 Web（同 machine） |
| R9 | Full-connection | Special components | ❌ | Console/MSF/Dispatcher 全连接（动态发现目标数） |
| R10 | Count | corporateserver / blserver | ❌ | corp=1；blserver≥SM 数 |
| R11 | Sequential | connectedTo | ❌ | 同类型 connectedTo 须连续 |
| R12 | Ref exists | 所有 connectedTo | ❌ | 目标 (component,machineName) 必须存在（悬空引用检查） |
| R13 | Count ≤1 | Dispatcher Client → Web | ❌ | dispatcherclient 连 Web 数 ≤1（>1 会被 DC 拒绝） |
| R14 | Direction | Web Tier → Gateway | ❌ | Web 不应反向连 Gateway（方向反了必错） |
| R15 | Symmetry | FSC → FSC | ⚠️ | FSC mesh 对称（A→B 则 B→A）；孤立 FSC 警告 |
| R16 | Type-level | tccs 两层 | ⚠️ | tccs 出向须含 corp+fsc+web；2tier/4tier 机器应有对应 tccs |
| R17 | Numeric | Server Manager pool | ❌/⚠️ | minWarm≤max；availableServerAt 非空 |
| R18 | Format | machineName | ❌ | 不应含 `@` / `://` / 空格 |
| R19 | Format | encrypted property | ⚠️ | encrypted=true 但值为空 |
| R20 | Format | 根节点 configName | ⚠️ | 缺失则警告 |

> 注：R3/R4 在 v3.1 由 err 降级为 warn——实测 div2 拓扑中 BL→Web 边由 DC 导入时自动生成，源 XML 中为空是正常状态，硬性报错会误杀可正常导入的配置。

## Dynamic Discovery

All validation is driven by XML content — no hardcoded hostnames or cluster definitions:

- **Clusters**: Built from `fnd0_serverManagerDisplayClusterId` on SM components
- **APP numbering**: Extracted from machineName via regex (works with any prefix like `APP01` or `jttcapp01` or `div2tcapp01` — 取**最后一个**数字串，避免前缀夹带的孤立数字被误当编号)
- **DISP identification**: Machines with `fnd0_dispatcherModule` component
- **DC identification**: BL servers not on SM or DISP machines
- **Corporate server**: Detected via `fnd0_corporateserver` component
- **FSC mesh**: 对称性动态检查，不假设固定主从拓扑（不同部署主从结构不同）
- **Full-connection components**: Found dynamically by component ID

## DC 导入行为与校验边界

结构校验通过 ≠ 一定能导入。Deployment Center 导入时会做以下运行时规范化，validator **不**据此报错：

- **自动裁剪**：部分 feature 属性（如 blserver 的 `fnd0_nxgraphicsbuilder_*`、corp 的 `tcoo_UseSponsoredAuth`、ftsIndexer 的 `cfg0_indexer_*` 等）导入后被移除。
- **自动加密**：所有 `encrypted="true"` 的密码属性在导入时按随机盐重加密（源 XML 中的明文/占位值在导出后变为密文，属预期）。
- **自动补连线**：`dispatcherclient`、部分 `blserver` 的 Web Tier 连线、以及个别瞬态连线（如 webtier→httpsconfig）由 DC 在导入/保存时自动生成或清除，源 XML 中为空或多余均属正常。

因此 R3/R4/R13 等对"DC 自动管理连线"的检查仅作警告，避免误杀合法配置。

## Component Count Standards (仅供参考，工具不依赖固定数量)

| 部署 | APP | FSC | 说明 |
|------|-----|-----|------|
| JT 基准 (原 56 APP 环境) | 56 | 86 (9 Master + 55 同机 + 22 cache) | README 旧标准，随拓扑变化 |
| BYD_DIV2 (v27) | 20 | 44 (4 Master + 40 cache) | 实际样本，验证用黄金标准 |

> 本工具**不**对组件总数做硬编码断言——加机器/减机器后直接跑即可。

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
