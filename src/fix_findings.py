import json

with open('notebooks/02_analysis_findings.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

updated_count = 0

# Find and update Finding 5 Key takeaway
for cell in nb['cells']:
    if cell['cell_type'] == 'markdown':
        source = ''.join(cell['source'])
        
        # Finding 5 update
        if 'Ketorolac is the central outlier within NSAIDs' in source:
            new_text = """**Key takeaway:**  
- **38 double-hit pairs** were found across 3 GC classes: NSAIDs (31), Triptans/선택적5-HT1수용체효능제 (6), and Ergot alkaloids/맥각알칼로이드계편두통치료제 (1).  
- **31 NSAID pairs carry dual regulatory signals**: all members of the GC NSAID class already face "functional duplication" risk (GC flag), but 31 specific pairings are *also* documented as absolute contraindications (AC edges), mostly for severe GI adverse events. This compounding signal is strongest.  
- **All triptans (Sumatriptan, Zolmitriptan, Naratriptan, Almotriptan, Frovatriptan) form a near-complete AC clique within their GC class** — any two triptans together risk additive vasoconstrictive crisis.  
- These pairs are the highest clinical priority in the dataset: two independent regulatory systems (GC + AC) are both flagging the same combinations, providing a compounded safety signal."""
            cell['source'] = [new_text]
            print("✓ Updated Finding 5")
            updated_count += 1
        
        # Finding 6 update
        if 'its risk is purely DDI-driven' in source:
            new_text = """**Key takeaway:**  
- **90 of 386 drugs (23.3%)** in the AC graph are also DC-flagged for dose caution.  
- Among the **top 20 hubs by degree**, 6 are also dose-caution: **SelegilineHydrochloride** (degree=40), **Ketorolac** (29), **Pimozide** (26), **Haloperidol** (24), **Amiodarone** (21), **Erythromycin** (16).  
- **Rifampicin** (degree=45, the top hub overall) is *not* DC-flagged in this dataset, while Ketorolac, Selegiline, and other top hubs are — suggesting their risk profile includes both DDI *and* dose-dependent safety concerns.  
- **Ketorolac** appears in both Finding 5 (double-hit NSAID pairs) and Finding 6 (high-degree dose-caution hub): it is the single most multiply-constrained drug in this dataset across multiple rule types.  
- This quadrant view provides a practical prescription triage framework: "High Degree + Dose Caution" drugs (red) require both a partner-avoidance check and a dosing review simultaneously."""
            cell['source'] = [new_text]
            print("✓ Updated Finding 6")
            updated_count += 1

with open('notebooks/02_analysis_findings.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"\nUpdated {updated_count} findings. Now re-executing notebook...")
