#!/usr/bin/env python3
"""Clear all existing analyses so next Grok run re-analyzes everything."""
import json, os, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

path = os.path.join(os.path.dirname(__file__), '..', 'veille-data.json')
with open(path, encoding='utf-8') as f:
    d = json.load(f)

before = sum(1 for a in d['articles'] if a.get('analysis'))
for a in d['articles']:
    a.pop('analysis', None)

with open(path, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print(f"Cleared {before} analyses. Ready for Grok re-run.")
