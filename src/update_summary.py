import json

with open('notebooks/02_analysis_findings.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell.get('id') == '56231d84':
        # Rebuild source cleanly - keep up to Finding 4, then add 5 and 6 once
        new_source = []
        for line in cell['source']:
            if '| 5 |' in line or '| 6 |' in line:
                continue
            new_source.append(line)
        # Ensure last line before appending ends with \n
        if new_source and not new_source[-1].endswith('\n'):
            new_source[-1] = new_source[-1] + '\n'
        new_source.append('| 5 | 38 pairs are both GC-overlapping AND AC-contraindicated | Ketorolac vs any NSAID and triptan vs triptan carry a compounded regulatory signal from two independent rule sources |\n')
        new_source.append('| 6 | 6 of top-20 hubs are also DC dose-caution drugs | Ketorolac appears in both F5 and F6 — most multiply-constrained drug across all rule types in this dataset |')
        cell['source'] = new_source
        print("Final summary:")
        print(''.join(new_source[-8:]))
        break

with open('notebooks/02_analysis_findings.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("\nDone.")
