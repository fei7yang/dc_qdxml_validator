# dc_qdxml_validator

Teamcenter Quick Deploy XML Connection Validation Rules

Defines 7 connection rules for validating TC Quick Deploy XML configurations. Used to verify that component connections (`<connectedTo>`) conform to the expected architecture topology.

## Validation Rules

| Rule | Type | Source → Target | Description |
|------|------|-----------------|-------------|
| R1 | Full-mesh (intra-cluster) | Web Tier → Server Manager | Each WT connects to all SMs in the same cluster |
| R2 | Odd/Even 1:1 | Gateway → VIS Pool Assigner | Odd-numbered Gateway → VIS01, Even → VIS02 |
| R3 | 1:1 | BL-Dispatcher → Web | DISP01→APP45, DISP02→APP46 |
| R4 | 1:1 | BL-DC → Web | DC01→APP47 |
| R5 | 1:1 | Dispatcher-4tier → Web | BYD_4TIER_PRD→APP52 |
| R6 | 1:1 | FTS Indexer → Web | aws2_ftsIndexer→APP52 |
| R7 | 1:1 | VIS Pool Assigner → Web | VIS01→APP52, VIS02→APP52 |

## Cluster Definitions

| Cluster | APP Range |
|---------|-----------|
| TcClusterJiTuan1 | APP01-10 |
| TcClusterJiTuan2 | APP11-20 |
| TcClusterJiTuan3 | APP21-30 |
| TcClusterJiTuan4 | APP31-38 |
| TcClusterHaiWai | APP39-40 |
| TcClusterXinJishuYuan | APP41-42 |
| TcClusterJiChuYuan | APP43-44 |
| TcClusterJieKou | APP45-52 |

## Rule Details

### R1: Web → Pool (Full-mesh intra-cluster)

- **Component**: `fnd0_j2ee_tcwebtier` → `fnd0_serverManager`
- **Rule**: Each WT connects to all SMs within the same cluster (full cross-connection)
- **Example**: APP01's WT → connects to APP01-10's SMs (10 links); APP45's WT → connects to APP45-52's SMs (8 links)
- **Validation**: WT should only keep `<connectedTo component="fnd0_serverManager">` entries within the same cluster; cross-cluster connections should be removed
- **Expected total**: 10×10 + 10×10 + 10×10 + 8×8 + 2×2 + 2×2 + 2×2 + 8×8 = **440 links**

### R2: Gateway → VisPoolAssigner (Odd/Even)

- **Component**: `aws2_client_gateway_webtier` → `aws2_vispoolassigner`
- **Rule**: Odd-numbered Gateway (01, 41) → VIS01; Even-numbered (02, 42) → VIS02

### R3: BL-Dispatcher → Web (1:1)

- **Component**: `fnd0_blserver` → `fnd0_j2ee_tcwebtier`
- **Rule**: DISP01→APP45, DISP02→APP46 (JieKou cluster)

### R4: BL-DC → Web (1:1)

- **Component**: `fnd0_blserver` → `fnd0_j2ee_tcwebtier`
- **Rule**: DC01→APP47 (JieKou cluster)

### R5: Dispatcher-4tier → Web (1:1)

- **Component**: `fnd0_dispatcherclient` → `fnd0_j2ee_tcwebtier`
- **Rule**: BYD_4TIER_PRD→APP52 (JieKou cluster)

### R6: Indexer → Web (1:1)

- **Component**: `aws2_ftsIndexer` → `fnd0_j2ee_tcwebtier`
- **Rule**: aws2_ftsIndexer→APP52 (JieKou cluster)

### R7: VisPoolAssigner → Web (1:1)

- **Component**: `aws2_vispoolassigner` → `fnd0_j2ee_tcwebtier`
- **Rule**: VIS01→APP52, VIS02→APP52 (JieKou cluster)

## File Structure

```
dc_qdxml_validator/
├── Validation.logic    # Human-readable validation rules (7 rules)
└── README.md
```

## Related Projects

- **[dc_qdxml_to_arch](https://github.com/fei7yang/dc_qdxml_to_arch)** — TC Quick Deploy XML → Architecture Visualization Tool

## License

Internal tool — for Teamcenter deployment validation.
