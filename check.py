#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dc_qdxml_validator — Teamcenter Quick Deploy XML 规则校验
"""
from lxml import etree
from collections import defaultdict
import sys, os

# 自动检测 XML 路径：有参数用参数，否则找脚本所在目录
if len(sys.argv) >= 2:
    INPUT = os.path.abspath(sys.argv[1])
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    xmls = sorted([f for f in os.listdir(base_dir) if f.lower().endswith('.xml')])
    if len(xmls) != 1:
        print(f'用法: python check.py [XML路径]  或把 .xml 放在 {base_dir}')
        sys.exit(1)
    INPUT = os.path.join(base_dir, xmls[0])

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

def get_cluster(app):
    for cname, apps in CLUSTERS.items():
        if app in apps:
            return cname, apps
    return None, []

def parse():
    p = etree.XMLParser(remove_blank_text=False, encoding='utf-8')
    return etree.parse(INPUT, p)

def get_components(tree, cid):
    """获取所有指定 id 的 component"""
    qdc = tree.getroot().find('quickDeployComponents')
    return [c for c in qdc if c.tag == 'component' and c.get('id') == cid]

def get_clients(tree, cid):
    """获取所有指定 id 的 client"""
    qcl = tree.getroot().find('quickDeployClients')
    return [c for c in qcl if c.tag == 'client' and c.get('id') == cid]

def get_block_servers(tree):
    """获取所有 blserver client"""
    qcl = tree.getroot().find('quickDeployClients')
    return [c for c in qcl if c.tag == 'client' and c.get('id') == 'fnd0_blserver']

def main():
    tree = parse()
    
    ok = 0
    warn = 0
    err = 0
    lines = []
    
    def add(status, msg):
        nonlocal ok, warn, err
        symbol = '✅' if status == 'ok' else ('⚠️' if status == 'warn' else '❌')
        lines.append(f"  {symbol} {msg}")
        if status == 'ok': ok += 1
        elif status == 'warn': warn += 1
        else: err += 1
    
    def section(title):
        lines.append('')
        lines.append(f'═══ {title} ═══')
    
    # ============ R1: Web → Pool ============
    section('规则1: Web → Pool (full-mesh intra-cluster)')
    webs = get_components(tree, 'fnd0_j2ee_tcwebtier')
    pools = get_components(tree, 'fnd0_serverManager')
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

    # ============ R2: Gateway → VisPoolAssigner ============
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

    # ============ R3: BL Server-Dispatcher → Web ============
    section('规则3: BL Server-Dispatcher → Web')
    bl_servers = get_block_servers(tree)
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

    # ============ R4: BL Server-DC → Web ============
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

    # ============ R5: Dispatcher Client-4tier → Web ============
    section('规则5: Dispatcher Client-4tier → Web')
    fourtier = get_clients(tree, 'fnd0_4tierrichclient')
    for ft in fourtier:
        web_conns = [ct.get('machineName') for ct in ft.findall('connectedTo') 
                     if ct.get('component') == 'fnd0_j2ee_tcwebtier']
        if web_conns:
            add('ok', f'4tier Client → Web {web_conns} ✓')
        else:
            add('err', f'4tier Client 未连接Web')

    # ============ R6: Indexer → Web ============
    section('规则6: FTS Indexer → Web')
    indexers = get_components(tree, 'aws2_ftsIndexer')
    for idx in indexers:
        web_conns = [ct.get('machineName') for ct in idx.findall('connectedTo')
                     if ct.get('component') == 'fnd0_j2ee_tcwebtier']
        if web_conns:
            add('ok', f'FTS Indexer → Web {web_conns} ✓')
        else:
            add('err', f'FTS Indexer 未连接Web')

    # ============ R7: VisPoolAssigner → Web ============
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

    # ============ R9: 全连接组件 ============
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
        for c in get_components(tree, cid) if cid != 'fnd0_dispatcherModule' else (lambda qdc=get_components(tree, cid): [x for x in qdc if x.get('machineName') == machine])():
            if c.get('machineName') != machine: continue
            actual = len([ct for ct in c.findall('connectedTo') if ct.get('component') == ctype])
            if actual == expected:
                add('ok', f'{cid} {machine} {desc}: {actual}/{expected} ✓')
            else:
                add('err', f'{cid} {machine} {desc}: {actual}/{expected}')
            break
    
    # ============ R10: 组件数量约定 ============
    section('规则10: 组件数量约定')
    corps = get_components(tree, 'fnd0_corporateserver')
    if len(corps) == 1:
        add('ok', f'corporateserver: 1个 ✓')
    else:
        add('err', f'corporateserver: {len(corps)}个 (应为1)')
    
    bls_count = len(get_clients(tree, 'fnd0_blserver'))
    if bls_count >= sm_total:
        add('ok', f'blserver: {bls_count}个 ≥ SM({sm_total}) ✓')
    else:
        add('err', f'blserver: {bls_count}个 < SM({sm_total})')
    
    # ============ 格式检查 ============
    section('格式检查')
    import re
    with open(INPUT, 'r', encoding='utf-8') as f:
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

    # ============ R11: connectedTo 类型分组 ============
    section('规则11: 同组件内 connectedTo 类型分组')
    group_issues = 0
    for c in tree.getroot().find('quickDeployComponents'):
        if c.tag != 'component': continue
        cid = c.get('id', '')
        machine = c.get('machineName', '')
        cts = c.findall('connectedTo')
        if len(cts) < 2: continue
        
        # 检查每种类型是否连续
        last_seen = {}
        for i, ct in enumerate(cts):
            ct_type = ct.get('component', '')
            if ct_type in last_seen and last_seen[ct_type] < i - 1:
                # 该类型之前出现过，且中间有其他类型
                # 检查中间是否有同类型
                for j in range(last_seen[ct_type] + 1, i):
                    if cts[j].get('component', '') == ct_type:
                        break
                else:
                    group_issues += 1
                    add('err', f'{cid} {machine}: {ct_type} 不连续 (idx={last_seen[ct_type]}→{i})')
                    break  # 一个组件只报一次
            last_seen[ct_type] = i
    
    if group_issues == 0:
        add('ok', f'所有组件 connectedTo 同类型连续 ✓')

    # ============ 总结 ============
    section('总结')
    lines.append(f'  ✅ 通过: {ok}')
    lines.append(f'  ❌ 错误: {err}')
    lines.append(f'  ⚠️ 警告: {warn}')
    
    return '\n'.join(lines), err

if __name__ == '__main__':
    report, errors = main()
    print(report)
    print(f'\n退出码: {errors} (有任何错误)')
