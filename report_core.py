#!/usr/bin/env python3
"""通用报告核心 — 被各 report_xxx.py 导入"""
from lxml import etree
from collections import defaultdict
import re, os

import sys

# 自动检测：脚本所在目录
_base_dir = os.path.dirname(os.path.abspath(__file__))
# XML 路径：1) 命令行参数, 2) 同目录唯一 .xml
if len(sys.argv) >= 2:
    INPUT = os.path.abspath(sys.argv[1])
else:
    _xmls = sorted([f for f in os.listdir(_base_dir) if f.lower().endswith('.xml')])
    INPUT = os.path.join(_base_dir, _xmls[0]) if len(_xmls) == 1 else ''
OUTDIR = _base_dir

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

def get_cluster(app):
    for cn, apps in CLUSTERS.items():
        if app in apps: return cn
    return '-'

def parse():
    p = etree.XMLParser(remove_blank_text=False, encoding='utf-8')
    return etree.parse(INPUT, p)

def condense_machines(machines):
    """按前缀分组压缩机器名：APP01-56, FSC01-08, BACache01-02, ..."""
    if not machines: return ''
    # Group by prefix (non-digit part)
    groups = defaultdict(list)
    for m in machines:
        m2 = re.search(r'(\D+)(\d+)', m)
        if m2:
            groups[m2.group(1)].append(int(m2.group(2)))
        else:
            groups[m].append(None)  # no number, keep as-is
    ranges = []
    for prefix in sorted(groups.keys()):
        nums = sorted(n for n in groups[prefix] if n is not None)
        no_nums = [k for k, v in groups.items() if k == prefix and None in v and not nums]
        if no_nums:
            ranges.append(prefix)
            continue
        if not nums:
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
        short = ct_type.replace('fnd0_','').replace('aws2_','').replace('client_gateway_','gw_')
        condensed = condense_machines(groups[ct_type])
        parts.append(f'{short}&rarr;{condensed}')
    return '<br>'.join(parts)

def generate(cid, is_client=False):
    tree = parse()
    parent = tree.getroot().find('quickDeployClients') if is_client else tree.getroot().find('quickDeployComponents')
    tag = 'client' if is_client else 'component'
    
    items = sorted([c for c in parent if c.tag == tag and c.get('id') == cid], key=lambda x: x.get('machineName'))
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
        item_var_props[machine] = {p.get('id'): p.get('value') for p in c.findall('property') if p.get('id') in var_props}
    
    var_check = {}
    for pid, vals in var_props.items():
        all_ok = True; checkable = True
        for v in vals:
            if not any(app in v for app in [c.get('machineName') for c in items if c.get('machineName')]):
                checkable = False; break
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
        machine = c.get('machineName')
        cluster = get_cluster(machine) if not is_client and machine.startswith('APP') else '-'
        cts = [(ct.get('component'), ct.get('machineName')) for ct in c.findall('connectedTo')]
        
        is_ok = True; problems = []
        
        if cid == 'fnd0_serverManager':
            expected = {('fnd0_servermgrconsole','APP01'), ('fnd0_serverpool_DBConfig','DBSCAN'), ('fnd0_tcdbserver','DBSCAN')}
            actual = set(cts)
            is_ok = (actual == expected)
            if not is_ok:
                problems.append(f'缺{expected-actual}' if expected-actual else f'多{actual-expected}')
        elif cid == 'fnd0_j2ee_tcwebtier':
            capps = CLUSTERS.get(cluster, [])
            sm_ok = set(m for t,m in cts if t=='fnd0_serverManager') == set(capps)
            has_ms = ('fnd0_microservice','MSF01') in cts
            has_console = ('fnd0_servermgrconsole','APP01') in cts
            is_ok = sm_ok and has_ms and has_console
            if not sm_ok: 
                missing = set(capps)-set(m for t,m in cts if t=="fnd0_serverManager")
                extra = set(m for t,m in cts if t=="fnd0_serverManager")-set(capps)
                problems.append(f'SM缺{missing}' if missing else f'SM多{extra}')
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
<title>{cid} 报告</title>
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

<h1>{cid}</h1>
<p>{len(items)} 个 | {len(prop_values)} 属性 (static={len(static_props)} var={len(var_props)}) | <span class="{"good" if err_count==0 else "bad"}">{err_count} 连接异常</span></p>

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
            machine = c.get('machineName')
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
        ct_str = format_cts(d['cts']) if len(d['cts']) > 2 else ', '.join([f'{t}&rarr;{m}' for t,m in d['cts']])
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
        html += f'</tr>\n'
    
    html += '</table>\n</body>\n</html>'
    
    out = os.path.join(OUTDIR, f'report_{cid}.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    
    n = len(items); s = len(static_props); v = len(var_props); ok = sum(1 for d in ct_data if d['is_ok'])
    status = '✓' if ok==n else f'⚠{n-ok}'
    print(f'  {cid}: {n}个 {s}st+{v}var ct={ok}/{n} {status}')
    return n

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python report_core.py <component_id> [--client]")
        sys.exit(1)
    cid = sys.argv[1]
    is_client = '--client' in sys.argv
    generate(cid, is_client)
