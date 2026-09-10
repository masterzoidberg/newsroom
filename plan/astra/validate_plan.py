"""Read-only consistency checks for the Astra planning documents; no runtime access."""
from pathlib import Path
import json
import re
import subprocess

root = Path(__file__).resolve().parent
repo = root.parent.parent
tasks = json.loads((root / 'task-index.json').read_text(encoding='utf-8'))
ledger = (root / 'TASKS.md').read_text(encoding='utf-8')
errors = []
by_id = {t['id']: t for t in tasks}
historical = {f'AST-{n:02}' for n in range(1, 5)}
all_ids = set(by_id) | historical | {'AST-12','AST-13','AST-14','AST-15','AST-19'}
ready = [t['id'] for t in tasks if t['status'] == 'READY']
if ready != ['AST-33']: errors.append(f'Unexpected READY tasks: {ready}')
if ledger.count('- **Status:** READY') != 1: errors.append('Ledger READY count')
visited, active = set(), set()

def visit(task_id):
    if task_id in active:
        errors.append('Dependency cycle at ' + task_id)
        return
    if task_id in visited or task_id in historical: return
    active.add(task_id)
    for dep in re.findall(r'AST-\d+', by_id[task_id]['deps']):
        if dep not in by_id and dep not in historical:
            errors.append(task_id + ' unresolved dependency ' + dep)
        else: visit(dep)
    active.remove(task_id)
    visited.add(task_id)

headings = ['GOAL','WHY','STARTING STATE','READ FIRST','SCOPE','NON-GOALS','PRODUCT CONTRACT','TECHNICAL CONTRACT','UX CONTRACT','IMPLEMENTATION GUIDANCE','FILES/SUBSYSTEMS','TESTS','BROWSER/VISUAL VERIFICATION','ACCEPTANCE CRITERIA','COST / PROVIDER SAFETY','GIT / WORKTREE SAFETY','AUTONOMY','ESCALATION CONDITIONS','COMPLETION REPORT','STOP CONDITION']
for t in tasks:
    visit(t['id'])
    match = re.search(r'^## ' + t['id'] + r' — .*?$(.*?)(?=^## AST-|\Z)', ledger, re.M | re.S)
    if not match:
        errors.append(t['id'] + ' missing ledger section')
        continue
    section = match.group(0)
    for key, value in [('Status',t['status']),('Dependencies',t['deps'])]:
        if f'- **{key}:** {value}' not in section:
            errors.append(t['id'] + ' snapshot/ledger mismatch: ' + key)
    for key in ['approach','accept','tests','files']:
        if not t[key] or t[key] not in section:
            errors.append(t['id'] + ' snapshot/ledger mismatch: ' + key)
    if t['prompt']:
        p = root / t['prompt']
        if not p.exists(): errors.append('Missing prompt ' + str(p)); continue
        content = p.read_text(encoding='utf-8')
        for h in headings:
            if '\n## '+h+'\n' not in content: errors.append(p.name+' missing '+h)
        if t['id'] not in content or t['deps'] not in content:
            errors.append(p.name + ' identity/dependency mismatch')

current_prompts = list((root/'prompts').glob('AST-*.md'))
if len(current_prompts) != 6: errors.append('Current prompt count must be six')
if len(re.findall(r'^\| C\d\d ', (root/'FEATURE_GAP_ANALYSIS.md').read_text(encoding='utf-8'), re.M)) !=30:
    errors.append('Capability count must be thirty')

# Canonical links, including preserved branch history. Original archive/_OLD
# contents are intentionally historical; do not rewrite them to hide history.
checked = 0
for p in root.rglob('*.md'):
    if '_OLD' in p.stem or 'archive' in p.parts or 'superseded' in p.parts: continue
    text = p.read_text(encoding='utf-8')
    for link in re.findall(r'\]\(([^)]+)\)', text):
        if '://' in link or link.startswith('#'): continue
        dest = (p.parent/link.split('#')[0].strip('<>')).resolve()
        checked +=1
        if not dest.exists(): errors.append(str(p.relative_to(root))+' broken link '+link)

for n in range(1,23):
    folder='archive' if n<=4 else 'superseded'
    path=f'prompts/{folder}/AST-{n:02}.md'
    before=subprocess.check_output(['git','show',f'3d7f9cf:plan/astra/prompts/AST-{n:02}.md'],cwd=repo).decode().replace('\r\n','\n')
    after=(root/path).read_text(encoding='utf-8').replace('\r\n','\n')
    if before != after: errors.append('Original prompt changed: '+path)

manifest=json.loads((root/'CHANGE_MANIFEST.json').read_text(encoding='utf-8'))
for original,old in manifest['preserved']:
    before=subprocess.check_output(['git','show',f'3d7f9cf:plan/astra/{original}'],cwd=repo).decode().replace('\r\n','\n').rstrip('\n')
    after=(root/old).read_text(encoding='utf-8').replace('\r\n','\n').rstrip('\n')
    if before !=after: errors.append('Preserved original changed: '+old)

changed=subprocess.check_output(['git','diff','--name-only'],cwd=repo).decode().splitlines()
if any(not (x.startswith('plan/astra/') or x.startswith('plan/plan-rework/')) for x in changed): errors.append('Tracked change outside planning scope')
if subprocess.check_output(['git','diff','--cached','--name-only'],cwd=repo).strip(): errors.append('Unexpected staged changes')
print(json.dumps({'result':'FAIL' if errors else 'PASS','future_records':len(tasks),'ready':ready,'current_prompts':len(current_prompts),'canonical_links_checked':checked,'preserved_originals':len(manifest['preserved']),'original_prompts_verified':22,'errors':errors},indent=2))
raise SystemExit(bool(errors))
