#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dc_qdxml_validator — Teamcenter Quick Deploy XML 校验工具
用法:
  dc_qdxml_validator [XML路径]           仅运行规则校验 (check模式)
  dc_qdxml_validator [XML路径] --all     校验 + 生成所有报告 + index.html
  dc_qdxml_validator [XML路径] --report <cid> [--client]  生成单个报告

XML路径:
  不指定时自动查找 exe/脚本所在目录的唯一 .xml 文件
  找到0个或多个时报错，需手动指定

示例:
  dc_qdxml_validator                          自动检测当前目录XML
  dc_qdxml_validator D:\\myfile.xml           检查指定XML
  dc_qdxml_validator D:\\myfile.xml --all     校验并生成全量报告
  dc_qdxml_validator D:\\myfile.xml --report fnd0_serverManager
  dc_qdxml_validator D:\\myfile.xml --report fnd0_blserver --client
"""
import sys
import os
import re
from lxml import etree
from collections import defaultdict

# Windows console UTF-8 输出（解决 GBK 无法显示 emoji 的问题）
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ===== 默认路径 =====
# 不硬编码桌面路径，自动查找 exe/脚本所在目录的 .xml 文件

# ===== Cluster 定义 =====
CLUSTERS = {
    'TcClusterJiTuan1':    [f'APP{i:02d}' for i in range(1, 11)],
    'TcClusterJiTuan2':    [f'APP{i:02d}' for i in range(11, 21)],
    'TcClusterJiTuan3':    [f'APP{i:02d}' for i in range(21, 31)],
    'TcClusterJiTuan4':    [f'APP{i:02d}' for i in range(31, 41)],
    'TcClusterXinJishuYuan': [f'APP{i:02d}' for i in range(41, 43)],
    'TcClusterJiChuYuan':  [f'APP{i:02d}' for i in range(43, 45)],
    'TcClusterJieKou':     [f'APP{i:02d}' for i in range(45, 53)],
    'TcClusterTest':       [f'APP{i:02d}' for i in range(53, 55)],
    'TcClusterHaiWai':     [f'APP{i:02d}' for i in range(55, 57)],
}

# ===== 全量报告组件列表 =====
COMPS = [
    'aws2_client_builder', 'aws2_client_gateway_webtier', 'aws2_ftsIndexer',
    'aws2_indexingengine', 'aws2_vispoolassigner', 'aws2_visservermanager',
    'aws2_zookeeper', 'fnd0_containerconfig', 'fnd0_corporateserver',
    'fnd0_dispatcherModule', 'fnd0_dispatcherScheduler', 'fnd0_dispatcherclient',
    'fnd0_fsc', 'fnd0_fsc_group', 'fnd0_fsc_keys', 'fnd0_httpsconfig',
    'fnd0_j2ee_tcwebtier', 'fnd0_licensingserver', 'fnd0_microservice',
    'fnd0_schdmgmt', 'fnd0_serverManager', 'fnd0_servermgrconsole',
    'fnd0_serverpool_DBConfig', 'fnd0_tcdbserver', 'fnd0_vault',
]
CLIENTS = [
    'eda0_client', 'fnd0_2tierrichclient', 'fnd0_4tierrichclient',
    'fnd0_blserver', 'fnd0_tccs',
]

# ===================================================================
# 共享工具函数
# ===================================================================

def get_cluster(app):
    for cname, apps in CLUSTERS.items():
        if app in apps:
            return cname, apps
    return None, []

def get_cluster_name(app):
    for cname, apps in CLUSTERS.items():
        if app in apps:
            return cname
    return '-'

def parse_xml(path):
    p = etree.XMLParser(remove_blank_text=False, encoding='utf-8')
    return etree.parse(path, p)

def get_config_name(xml_path):
    """读取 XML 的 configName 属性"""
    tree = etree.parse(xml_path)
    return tree.getroot().get('configName', 'Unknown')

def get_components(tree, cid):
    qdc = tree.getroot().find('quickDeployComponents')
    return [c for c in qdc if c.tag == 'component' and c.get('id') == cid]

def get_clients_by_id(tree, cid):
    qcl = tree.getroot().find('quickDeployClients')
    return [c for c in qcl if c.tag == 'client' and c.get('id') == cid]

def condense_machines(machines):
    """按前缀分组压缩机器名: APP01-56, FSC01-08, ..."""
    if not machines:
        return ''
    groups = defaultdict(list)
    for m in machines:
        m2 = re.search(r'(\D+)(\d+)', m)
        if m2:
            groups[m2.group(1)].append(int(m2.group(2)))
        else:
            groups[m].append(None)
    ranges = []
    for prefix in sorted(groups.keys()):
        nums = sorted(n for n in groups[prefix] if n is not None)
        if not nums:
            ranges.append(prefix)
            continue
        start = end = nums[0]
        for n in nums[1:]:
            if n == end + 1:
                end = n
            else:
                r = f'{prefix}{start:02d}' if start == end else f'{prefix}{start:02d}-{end:02d}'
                ranges.append(r)
                start = end = n
        r = f'{prefix}{start:02d}' if start == end else f'{prefix}{start:02d}-{end:02d}'
        ranges.append(r)
    return ', '.join(ranges)

def format_cts(cts):
    groups = {}
    for ct_type, machine in cts:
        groups.setdefault(ct_type, []).append(machine)
    parts = []
    for ct_type in sorted(groups.keys()):
        short = ct_type.replace('fnd0_', '').replace('aws2_', '').replace('client_gateway_', 'gw_')
        condensed = condense_machines(groups[ct_type])
        parts.append(f'{short}&rarr;{condensed}')
    return '<br>'.join(parts)

# ===================================================================
# CHECK 模式
# ===================================================================

def run_check(xml_path):
    tree = parse_xml(xml_path)
    ok = warn = err = 0
    lines = []

    def add(status, msg):
        nonlocal ok, warn, err
        symbol = '✅' if status == 'ok' else ('⚠️' if status == 'warn' else '❌')
        lines.append(f'  {symbol} {msg}')
        if status == 'ok': ok += 1
        elif status == 'warn': warn += 1
        else: err += 1

    def section(title):
        lines.append('')
        lines.append(f'═══ {title} ═══')

    # R1
    section('规则1: Web → Pool (full-mesh intra-cluster)')
    webs = get_components(tree, 'fnd0_j2ee_tcwebtier')
    total_connections = 0
    for web in webs:
        machine = web.get('machineName')
        cname, capps = get_cluster(machine)
        if not capps:
            add('warn', f'{machine} 不在已知cluster中')
            continue
        sm_conns = [ct.get('machineName') for ct in web.findall('connectedTo')
                    if ct.get('component') == 'fnd0_serverManager']
        expected = capps
        total_connections += len(sm_conns)
        missing = set(expected) - set(sm_conns)
        extra = set(sm_conns) - set(expected)
        if not missing and not extra:
            add('ok', f'{machine} ({cname}) → {len(sm_conns)}/{len(expected)} Pool ✓')
        else:
            msg = f'{machine} ({cname}) → {len(sm_conns)}/{len(expected)} Pool'
            if missing: msg += f' 缺{missing}'
            if extra: msg += f' 多{extra}'
            add('err', msg)
    add('ok', f'连线总数: {total_connections}/480 (预期480)')

    # R2
    section('规则2: Gateway → VisPoolAssigner (奇偶配对)')
    gateways = get_components(tree, 'aws2_client_gateway_webtier')
    for gw in gateways:
        machine = gw.get('machineName')
        num = int(machine[3:])
        expected_vis = 'VIS01' if num % 2 == 1 else 'VIS02'
        vis_conns = [ct.get('machineName') for ct in gw.findall('connectedTo')
                     if ct.get('component') == 'aws2_vispoolassigner']
        if expected_vis in vis_conns and len(vis_conns) == 1:
            add('ok', f'{machine} → {expected_vis} ✓')
        else:
            add('err', f'{machine} → {vis_conns} (期望{expected_vis})')

    # R3
    section('规则3: BL Server-Dispatcher → Web')
    bl_servers = get_clients_by_id(tree, 'fnd0_blserver')
    for bl in bl_servers:
        machine = bl.get('machineName')
        if machine not in ('DISP01', 'DISP02'):
            continue
        web_conns = [ct.get('machineName') for ct in bl.findall('connectedTo')
                     if ct.get('component') == 'fnd0_j2ee_tcwebtier']
        expected = 'APP45' if machine == 'DISP01' else 'APP46'
        if expected in web_conns and len(web_conns) >= 1:
            add('ok', f'{machine} BL → Web {web_conns} ✓')
        else:
            add('err', f'{machine} BL → Web {web_conns} (期望{expected})')

    # R4
    section('规则4: BL Server-DC → Web')
    for bl in bl_servers:
        machine = bl.get('machineName')
        if machine != 'DC01':
            continue
        web_conns = [ct.get('machineName') for ct in bl.findall('connectedTo')
                     if ct.get('component') == 'fnd0_j2ee_tcwebtier']
        if 'APP47' in web_conns and len(web_conns) >= 1:
            add('ok', f'DC01 BL → Web {web_conns} ✓')
        else:
            add('err', f'DC01 BL → Web {web_conns} (期望APP47)')

    # R5
    section('规则5: Dispatcher Client-4tier → Web')
    fourtier = get_clients_by_id(tree, 'fnd0_4tierrichclient')
    for ft in fourtier:
        web_conns = [ct.get('machineName') for ct in ft.findall('connectedTo')
                     if ct.get('component') == 'fnd0_j2ee_tcwebtier']
        if web_conns:
            add('ok', f'4tier Client → Web {web_conns} ✓')
        else:
            add('err', '4tier Client 未连接Web')

    # R6
    section('规则6: FTS Indexer → Web')
    indexers = get_components(tree, 'aws2_ftsIndexer')
    for idx in indexers:
        web_conns = [ct.get('machineName') for ct in idx.findall('connectedTo')
                     if ct.get('component') == 'fnd0_j2ee_tcwebtier']
        if web_conns:
            add('ok', f'FTS Indexer → Web {web_conns} ✓')
        else:
            add('err', 'FTS Indexer 未连接Web')

    # R7
    section('规则7: VisPoolAssigner → Web')
    viss = get_components(tree, 'aws2_vispoolassigner')
    for vis in viss:
        machine = vis.get('machineName')
        web_conns = [ct.get('machineName') for ct in vis.findall('connectedTo')
                     if ct.get('component') == 'fnd0_j2ee_tcwebtier']
        if web_conns:
            add('ok', f'{machine} → Web {web_conns} ✓')
        else:
            add('err', f'{machine} 未连接Web')

    # R9
    section('规则9: 全连接组件 (新增APP时须同步)')
    web_total = len(get_components(tree, 'fnd0_j2ee_tcwebtier'))
    sm_total = len(get_components(tree, 'fnd0_serverManager'))
    checks = [
        ('fnd0_servermgrconsole', 'APP01', 'fnd0_serverManager', sm_total, 'SM全连接'),
        ('fnd0_servermgrconsole', 'APP01', 'fnd0_j2ee_tcwebtier', web_total, 'Web全连接'),
        ('fnd0_microservice', 'MSF01', 'fnd0_j2ee_tcwebtier', web_total, 'Web全连接'),
        ('fnd0_dispatcherModule', 'DISP01', 'fnd0_j2ee_tcwebtier', web_total, 'Web全连接'),
        ('fnd0_dispatcherModule', 'DISP02', 'fnd0_j2ee_tcwebtier', web_total, 'Web全连接'),
    ]
    for cid, machine, ctype, expected, desc in checks:
        candidates = get_components(tree, cid)
        for c in candidates:
            if c.get('machineName') != machine:
                continue
            actual = len([ct for ct in c.findall('connectedTo') if ct.get('component') == ctype])
            if actual == expected:
                add('ok', f'{cid} {machine} {desc}: {actual}/{expected} ✓')
            else:
                add('err', f'{cid} {machine} {desc}: {actual}/{expected}')
            break

    # R10
    section('规则10: 组件数量约定')
    corps = get_components(tree, 'fnd0_corporateserver')
    if len(corps) == 1:
        add('ok', 'corporateserver: 1个 ✓')
    else:
        add('err', f'corporateserver: {len(corps)}个 (应为1)')
    bls_count = len(get_clients_by_id(tree, 'fnd0_blserver'))
    if bls_count >= sm_total:
        add('ok', f'blserver: {bls_count}个 ≥ SM({sm_total}) ✓')
    else:
        add('err', f'blserver: {bls_count}个 < SM({sm_total})')

    # 格式检查
    section('格式检查')
    with open(xml_path, 'r', encoding='utf-8') as f:
        file_lines = f.readlines()
    fmt_issues = 0
    for i, line in enumerate(file_lines):
        if re.search(r'</\w+>\s*<\w+', line) and '<?xml' not in line:
            stripped = line.strip()
            if not stripped.startswith('<!--'):
                add('err', f'同行标签 行{i+1}: {stripped[:80]}...')
                fmt_issues += 1
    if fmt_issues == 0:
        add('ok', '无同行标签问题 ✓')

    # R11
    section('规则11: 同组件内 connectedTo 类型分组')
    group_issues = 0
    for c in tree.getroot().find('quickDeployComponents'):
        if c.tag != 'component':
            continue
        cid_val = c.get('id', '')
        machine = c.get('machineName', '')
        cts = c.findall('connectedTo')
        if len(cts) < 2:
            continue
        last_seen = {}
        for i, ct in enumerate(cts):
            ct_type = ct.get('component', '')
            if ct_type in last_seen and last_seen[ct_type] < i - 1:
                for j in range(last_seen[ct_type] + 1, i):
                    if cts[j].get('component', '') == ct_type:
                        break
                else:
                    group_issues += 1
                    add('err', f'{cid_val} {machine}: {ct_type} 不连续 (idx={last_seen[ct_type]}→{i})')
                    break
            last_seen[ct_type] = i
    if group_issues == 0:
        add('ok', '所有组件 connectedTo 同类型连续 ✓')

    # 总结
    section('总结')
    lines.append(f'  ✅ 通过: {ok}')
    lines.append(f'  ❌ 错误: {err}')
    lines.append(f'  ⚠️ 警告: {warn}')

    return '\n'.join(lines), err

# ===================================================================
# REPORT 模式
# ===================================================================

def generate_report(xml_path, out_dir, cid, is_client=False):
    config_name = get_config_name(xml_path)
    tree = parse_xml(xml_path)
    parent = (tree.getroot().find('quickDeployClients') if is_client
              else tree.getroot().find('quickDeployComponents'))
    tag = 'client' if is_client else 'component'

    items = sorted([c for c in parent if c.tag == tag and c.get('id') == cid],
                   key=lambda x: x.get('machineName', ''))
    if not items:
        print(f'{cid}: 0 items, skip')
        return 0

    prop_values = defaultdict(set)
    for c in items:
        for p in c.findall('property'):
            prop_values[p.get('id')].add(p.get('value'))

    static_props = {k: list(v)[0] for k, v in prop_values.items() if len(v) == 1}
    var_props = {k: sorted(v) for k, v in prop_values.items() if len(v) > 1}

    item_var_props = {}
    for c in items:
        machine = c.get('machineName')
        item_var_props[machine] = {
            p.get('id'): p.get('value')
            for p in c.findall('property') if p.get('id') in var_props
        }

    var_check = {}
    for pid, vals in var_props.items():
        all_ok = True
        checkable = True
        for v in vals:
            if not any(c.get('machineName', '') in v for c in items):
                checkable = False
                break
        if not checkable:
            var_check[pid] = '无法检测'
        else:
            for c in items:
                machine = c.get('machineName')
                vals2 = [p.get('value') for p in c.findall('property') if p.get('id') == pid]
                if vals2 and machine not in vals2[0]:
                    all_ok = False
            var_check[pid] = '✓ 模式一致' if all_ok else '✗ 存在偏差'

    ct_data = []
    for c in items:
        machine = c.get('machineName', '')
        cluster = (get_cluster_name(machine)
                   if not is_client and machine.startswith('APP') else '-')
        cts = [(ct.get('component'), ct.get('machineName')) for ct in c.findall('connectedTo')]

        is_ok = True
        problems = []

        if cid == 'fnd0_serverManager':
            expected = {('fnd0_servermgrconsole', 'APP01'),
                        ('fnd0_serverpool_DBConfig', 'DBSCAN'),
                        ('fnd0_tcdbserver', 'DBSCAN')}
            actual = set(cts)
            is_ok = (actual == expected)
            if not is_ok:
                if expected - actual: problems.append(f'缺{expected-actual}')
                if actual - expected: problems.append(f'多{actual-expected}')
        elif cid == 'fnd0_j2ee_tcwebtier':
            capps = CLUSTERS.get(cluster, [])
            sm_ok = set(m for t, m in cts if t == 'fnd0_serverManager') == set(capps)
            has_ms = ('fnd0_microservice', 'MSF01') in cts
            has_console = ('fnd0_servermgrconsole', 'APP01') in cts
            is_ok = sm_ok and has_ms and has_console
            if not sm_ok:
                sm_actual = set(m for t, m in cts if t == 'fnd0_serverManager')
                missing = set(capps) - sm_actual
                extra = sm_actual - set(capps)
                if missing: problems.append(f'SM缺{missing}')
                if extra: problems.append(f'SM多{extra}')
            if not has_ms: problems.append('缺MSF01')
            if not has_console: problems.append('缺console')

        ct_data.append({
            'machine': machine, 'cluster': cluster, 'ct_count': len(cts),
            'cts': cts, 'is_ok': is_ok, 'problems': problems
        })

    err_count = sum(1 for d in ct_data if not d['is_ok'])

    html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>{config_name} — {cid}</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }}
h1 {{ color: #1a237e; }}
h2 {{ color: #283593; border-bottom: 2px solid #283593; padding-bottom: 4px; margin-top: 28px; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; background: white; box-shadow: 0 2px 4px rgba(0,0,0,.1); }}
th {{ background: #1a237e; color: white; padding: 8px 10px; text-align: left; font-size: 13px; position: sticky; top: 0; }}
td {{ padding: 6px 10px; font-size: 12px; border-bottom: 1px solid #e0e0e0; }}
tr:hover {{ background: #e8eaf6; }}
.bad {{ background: #ffebee !important; }}
.good {{ color: #2e7d32; font-weight: bold; }}
.warn {{ color: #ef6c00; }}
.unk {{ color: #9e9e9e; font-style: italic; }}
.prop-id {{ font-family: monospace; font-size: 11px; color: #555; }}
.prop-val {{ font-family: monospace; font-size: 11px; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.variable {{ background: #fff8e1 !important; }}
.pass {{ background: #e8f5e9 !important; }}
.fail {{ background: #ffebee !important; color: #c62828 !important; }}
.summary {{ display: flex; gap: 16px; margin-bottom: 16px; }}
.card {{ background: white; padding: 12px 20px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
.card .num {{ font-size: 28px; font-weight: bold; }}
.red {{ color: #c62828; }}
.green {{ color: #2e7d32; }}
.back {{ margin-bottom: 12px; }}
.back a {{ color: #1a237e; text-decoration: none; }}
</style>
</head>
<body>
<div class="back"><a href="index.html">&larr; 返回索引</a></div>
<h1>{config_name} — {cid}</h1>
<p>{len(items)} 个 | {len(prop_values)} 属性 (static={len(static_props)} var={len(var_props)}) | \
<span class="{"good" if err_count==0 else "bad"}">{err_count} 连接异常</span></p>
<div class="summary">
<div class="card"><div class="num green">{len(items)}</div>实例</div>
<div class="card"><div class="num">{len(static_props)}</div>静态</div>
<div class="card"><div class="num warn">{len(var_props)}</div>可变</div>
<div class="card"><div class="num {("green","red")[err_count>0]}">{sum(1 for d in ct_data if d["is_ok"])}/{len(items)}</div>连接</div>
</div>
'''
    if static_props:
        html += '<h2>1. 静态属性</h2><table><tr><th>#</th><th>属性 ID</th><th>值</th></tr>\n'
        for i, (pid, pval) in enumerate(sorted(static_props.items()), 1):
            html += f'<tr><td>{i}</td><td class="prop-id">{pid}</td><td class="prop-val">{pval}</td></tr>\n'
        html += '</table>\n'

    if var_props:
        html += '<h2>2. 可变属性</h2><table><tr><th>#</th><th>属性 ID</th><th>不同值</th><th>示例</th><th>模式检测</th></tr>\n'
        for i, (pid, vals) in enumerate(sorted(var_props.items()), 1):
            sample = ', '.join(list(vals)[:3])
            check = var_check.get(pid, '')
            ck_class = 'good' if '✓' in check else ('bad' if '✗' in check else 'unk')
            html += f'<tr class="variable"><td>{i}</td><td class="prop-id">{pid}</td><td>{len(vals)}</td>'
            html += f'<td class="prop-val">{sample}{"..." if len(vals)>3 else ""}</td>'
            html += f'<td class="{ck_class}">{check}</td></tr>\n'
        html += '</table>\n'

        html += '<h2>3. 可变属性逐机详情</h2><table><tr><th>机器</th>'
        for pid in sorted(var_props.keys()):
            html += f'<th class="prop-id" style="font-size:11px">{pid.split(".")[-1]}</th>'
        html += '</tr>\n'
        for c in items:
            machine = c.get('machineName', '')
            html += f'<tr><td><b>{machine}</b></td>'
            for pid in sorted(var_props.keys()):
                val = item_var_props.get(machine, {}).get(pid, '-')
                cls = 'pass' if machine in val else 'fail'
                html += f'<td class="{cls} prop-val" title="{val}">{val}</td>'
            html += '</tr>\n'
        html += '</table>\n'

    html += '''<h2>4. connectedTo</h2><table>
<tr><th>机器</th><th>Cluster</th><th>连接数</th><th>连接明细</th><th>状态</th><th>问题</th></tr>
'''
    for d in ct_data:
        ct_str = (format_cts(d['cts']) if len(d['cts']) > 2
                  else ', '.join([f'{t}&rarr;{m}' for t, m in d['cts']]))
        row_class = 'bad' if not d['is_ok'] else ''
        status = '✓' if d['is_ok'] else '✗'
        prob_str = '; '.join(d['problems'])
        html += f'<tr class="{row_class}">'
        html += f'<td><b>{d["machine"]}</b></td>'
        html += f'<td>{d["cluster"]}</td>'
        html += f'<td>{d["ct_count"]}</td>'
        html += f'<td style="font-size:11px;line-height:1.4">{ct_str}</td>'
        html += f'<td class="{"good" if d["is_ok"] else "bad"}">{status}</td>'
        html += f'<td style="font-size:10px;{"color:#c62828" if not d["is_ok"] else ""}">{prob_str}</td>'
        html += '</tr>\n'
    html += '</table>\n</body>\n</html>'

    out_path = os.path.join(out_dir, f'report_{cid}.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    n = len(items)
    s = len(static_props)
    v = len(var_props)
    ok_n = sum(1 for d in ct_data if d['is_ok'])
    status_str = '✓' if ok_n == n else f'⚠{n-ok_n}'
    print(f'  {cid}: {n}个 {s}st+{v}var ct={ok_n}/{n} {status_str}')
    return n

# ===================================================================
# ALL 模式 (校验 + 生成所有报告 + index.html)
# ===================================================================

def run_all(xml_path, out_dir):
    config_name = get_config_name(xml_path)
    # 先跑 check
    print('=' * 60)
    print('【校验规则】')
    print('=' * 60)
    report, errors = run_check(xml_path)
    print(report)

    # 生成全量报告
    print()
    print('=' * 60)
    print('【生成报告】')
    print('=' * 60)
    results = []
    for cid in COMPS:
        n = generate_report(xml_path, out_dir, cid, is_client=False)
        results.append((cid, 'component', n))
    for cid in CLIENTS:
        n = generate_report(xml_path, out_dir, cid, is_client=True)
        results.append((cid, 'client', n))

    # 生成 index.html
    items_html = ''
    for cid, ctype, count in results:
        html_file = f'report_{cid}.html'
        items_html += (f'<tr><td><a href="{html_file}">{cid}</a></td>'
                       f'<td>{ctype}</td><td>{count} 个实例</td></tr>\n')

    index_html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>{config_name} 报告索引</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 40px; background: #f5f5f5; }}
h1 {{ color: #1a237e; }}
table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 2px 4px rgba(0,0,0,.1); }}
th {{ background: #1a237e; color: white; padding: 10px 14px; text-align: left; font-size: 14px; }}
td {{ padding: 8px 14px; font-size: 13px; border-bottom: 1px solid #e0e0e0; }}
tr:hover {{ background: #e8eaf6; }}
a {{ color: #1a237e; text-decoration: none; font-weight: bold; }}
a:hover {{ text-decoration: underline; }}
.summary {{ margin-bottom: 20px; color: #666; }}
</style>
</head>
<body>
<h1>{config_name} 报告索引</h1>
<p class="summary">{len(COMPS)} components + {len(CLIENTS)} clients = {len(results)} 报告</p>
<table>
<tr><th>Component ID</th><th>类型</th><th>实例数</th></tr>
{items_html}
</table>
</body>
</html>'''

    index_path = os.path.join(out_dir, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_html)
    print(f'\nIndex: {index_path}')
    return errors

# ===================================================================
# 入口
# ===================================================================

def print_help():
    print(__doc__)

def main():
    args = sys.argv[1:]

    # 确定 exe/脚本所在目录
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # 解析 XML 路径
    xml_path = None
    remaining = []
    for a in args:
        if not a.startswith('--') and xml_path is None and os.path.isfile(a):
            xml_path = os.path.abspath(a)
        else:
            remaining.append(a)

    # 模式判断 — help 优先，不依赖 XML 是否存在
    if '--help' in remaining or '-h' in remaining:
        print_help()
        sys.exit(0)

    # 未指定 XML → 自动查找所在目录下的 .xml
    if xml_path is None:
        xmls = sorted([f for f in os.listdir(base_dir) if f.lower().endswith('.xml')])
        if len(xmls) == 0:
            print(f'❌ 所在目录无 .xml 文件: {base_dir}')
            print(f'   用法: dc_qdxml_validator [XML路径] [--all|--report <cid>]')
            sys.exit(1)
        if len(xmls) > 1:
            print(f'❌ 所在目录有多个 .xml 文件，请指定:')
            for x in xmls:
                print(f'   {x}')
            sys.exit(1)
        xml_path = os.path.join(base_dir, xmls[0])
        print(f'自动检测: {xmls[0]}')

    # 模式判断
    if not os.path.exists(xml_path):
        print(f'❌ 找不到 XML 文件: {xml_path}')
        sys.exit(1)

    # 输出目录 = exe/脚本所在目录（或 XML 所在目录）
    out_dir = base_dir
    cfg = get_config_name(xml_path)

    # 双击（无参数）默认 → --all 生成报告 + 打开浏览器
    if not remaining:
        remaining.append('--all')

    if '--all' in remaining:
        print(f'Config: {cfg}  ({xml_path})')
        print(f'输出目录: {out_dir}')
        errors = run_all(xml_path, out_dir)
        index_path = os.path.join(out_dir, 'index.html')
        print(f'\n📄 报告索引: {index_path}')
        import webbrowser
        webbrowser.open(f'file:///{index_path}')
        input('\n按 Enter 键退出...')
        sys.exit(errors)

    elif '--report' in remaining:
        idx = remaining.index('--report')
        if idx + 1 >= len(remaining):
            print('❌ --report 需要指定组件ID')
            sys.exit(1)
        cid = remaining[idx + 1]
        is_client = '--client' in remaining
        print(f'Config: {cfg}  ({xml_path})')
        generate_report(xml_path, out_dir, cid, is_client=is_client)
        html_path = os.path.join(out_dir, f'report_{cid}.html')
        print(f'\n📄 报告: {html_path}')
        input('\n按 Enter 键退出...')
        sys.exit(0)

    else:
        # 默认: check 模式
        print(f'Config: {cfg}  ({xml_path})')
        report, errors = run_check(xml_path)
        print(report)
        print()
        print(f'💡 --all 生成全量报告  |  --report <组件ID> 生成单个报告  |  --help 查看说明')
        input('\n按 Enter 键退出...')
        sys.exit(errors)


if __name__ == '__main__':
    main()
