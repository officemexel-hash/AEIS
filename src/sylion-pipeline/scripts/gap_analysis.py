"""Gap analysis: compare frontend client.ts paths with backend routes."""
import re
import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'dashboard')

# Extract paths from client.ts
with open('../sylion-frontend/src/lib/api/client.ts', 'r', encoding='utf-8') as f:
    content = f.read()

paths = set()
for m in re.finditer(r'request<[^>]*>\("([^"]+)"', content):
    path = m.group(1)
    base = path.split('?')[0]
    base = re.sub(r'\$\{[^}]+\}', '{id}', base)
    paths.add(base)

# Get backend routes
from sylion.api.app import app
backend_paths = set()
for route in app.routes:
    if hasattr(route, 'methods'):
        p = route.path
        backend_paths.add(p)

# Check matches
missing = []
for p in sorted(paths):
    if p in backend_paths:
        continue
    if p + '/' in backend_paths:
        continue
    found = False
    for bp in backend_paths:
        bp_pattern = re.sub(r'\{[^}]+\}', r'[^/]+', bp)
        if re.match('^' + bp_pattern + '$', p):
            found = True
            break
    if not found:
        missing.append(p)

print(f'Total frontend paths: {len(paths)}')
print(f'Missing paths: {len(missing)}')
print()
for p in missing[:80]:
    print(p)
if len(missing) > 80:
    print(f'... and {len(missing)-80} more')
