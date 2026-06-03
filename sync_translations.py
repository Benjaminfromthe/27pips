"""
Utility: regenerate translations.py from the three JSON locale files.
Run with: python sync_translations.py
This file is not used in production — i18n.py reads the JSON files directly.
translations.py is kept as a human-readable reference and legacy fallback.
"""
import json
from pathlib import Path

LOCALES = ['en', 'fr', 'rw']
OUT     = Path('translations.py')

data = {}
for lang in LOCALES:
    path = Path(f'locales/{lang}.json')
    data[lang] = json.loads(path.read_text(encoding='utf-8'))

lines = [
    '# ============================================================',
    '# 27pips — translations.py  |  EN / FR / RW localization',
    '# AUTO-GENERATED from locales/*.json — do not edit by hand.',
    '# Run: python sync_translations.py to regenerate.',
    '# Production i18n uses locales/*.json via i18n.py directly.',
    '# ============================================================',
    '',
    'TRANSLATIONS = {',
]

for lang in LOCALES:
    lines.append(f"    '{lang}': {{")
    entries = data[lang]
    items   = list(entries.items())
    for i, (k, v) in enumerate(items):
        comma = ',' if i < len(items) - 1 else ''
        # Escape backslashes and single quotes in value
        safe_v = str(v).replace('\\', '\\\\').replace("'", "\\'")
        lines.append(f"        '{k}': '{safe_v}'{comma}")
    lines.append('    },' if lang != LOCALES[-1] else '    },')

lines.append('}')
lines.append('')

OUT.write_text('\n'.join(lines), encoding='utf-8')
print(f"Written {OUT} with {sum(len(data[l]) for l in LOCALES)} total entries "
      f"({', '.join(str(len(data[l]))+' '+l for l in LOCALES)})")
