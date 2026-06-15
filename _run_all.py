#!/usr/bin/env python3
"""生成所有报告 + 索引页"""
import subprocess, os, sys

OUTDIR = r'C:\Eric_Workspace\dc_qdxml_validator'
PYTHON = r'C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe'

comps = [
    'aws2_client_builder','aws2_client_gateway_webtier','aws2_ftsIndexer',
    'aws2_indexingengine','aws2_vispoolassigner','aws2_visservermanager',
    'aws2_zookeeper','fnd0_containerconfig','fnd0_corporateserver',
    'fnd0_dispatcherModule','fnd0_dispatcherScheduler','fnd0_dispatcherclient',
    'fnd0_fsc','fnd0_fsc_group','fnd0_fsc_keys','fnd0_httpsconfig',
    'fnd0_j2ee_tcwebtier','fnd0_licensingserver','fnd0_microservice',
    'fnd0_schdmgmt','fnd0_serverManager','fnd0_servermgrconsole',
    'fnd0_serverpool_DBConfig','fnd0_tcdbserver','fnd0_vault',
]
clients = ['eda0_client','fnd0_2tierrichclient','fnd0_4tierrichclient','fnd0_blserver','fnd0_tccs']

results = []

print("Generating reports...")
for cid in comps:
    r = subprocess.run([PYTHON, f'report_{cid}.py'], cwd=OUTDIR, capture_output=True, text=True)
    results.append((cid, 'comp', r.stdout.strip()))
    print(r.stdout.strip())

for cid in clients:
    r = subprocess.run([PYTHON, f'report_{cid}.py'], cwd=OUTDIR, capture_output=True, text=True)
    results.append((cid, 'client', r.stdout.strip()))
    print(r.stdout.strip())

# Build index
items_html = ''
for cid, ctype, output in results:
    parts = output.split(': ')
    summary = parts[1] if len(parts) > 1 else output
    html_file = f'report_{cid}.html'
    items_html += f'<tr><td><a href="{html_file}">{cid}</a></td><td>{ctype}</td><td style="font-size:11px">{summary}</td></tr>\n'

index_html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>Teamcenter 报告索引</title>
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
<h1>Teamcenter 报告索引</h1>
<p class="summary">{len(comps)} components + {len(clients)} clients = {len(results)} 报告</p>
<table>
<tr><th>Component ID</th><th>类型</th><th>概要 (数量 st+var ct=OK/Total)</th></tr>
{items_html}
</table>
</body>
</html>'''

with open(os.path.join(OUTDIR, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(index_html)
print(f'\nIndex: {os.path.join(OUTDIR, "index.html")}')
