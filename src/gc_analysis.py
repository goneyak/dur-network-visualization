import pandas as pd

gc = pd.read_csv('data/raw/OpenData_PotOpenDurIngr_GC20260312.csv', encoding='utf-8-sig', low_memory=False)
edge = pd.read_csv('data/processed/ac_edge_table_english.csv')
node = pd.read_csv('data/processed/ac_node_table_with_overlay.csv')

print('=== GC 계열명 분포 (top 20) ===')
print(gc['계열명'].value_counts().head(20))

print('\n=== GC/AC 코드 교집합 ===')
gc_codes = set(gc['DUR성분코드'].dropna().astype(str))
ac_codes = set(node['code'].astype(str))
overlap = gc_codes & ac_codes
print(f'GC 고유 코드: {len(gc_codes)}, AC 고유 코드: {len(ac_codes)}, 교집합: {len(overlap)}')

print('\n=== 같은 계열명 내에서 AC 엣지가 있는 쌍 ===')
class_to_codes = gc.groupby('계열명')['DUR성분코드'].apply(set).to_dict()

double_hit_pairs = []
for cls, codes in class_to_codes.items():
    codes = [str(c) for c in codes]
    for i, c1 in enumerate(codes):
        for c2 in codes[i+1:]:
            match = edge[
                ((edge['source_code'].astype(str) == c1) & (edge['target_code'].astype(str) == c2)) |
                ((edge['source_code'].astype(str) == c2) & (edge['target_code'].astype(str) == c1))
            ]
            if len(match) > 0:
                row = match.iloc[0]
                double_hit_pairs.append({
                    'class': cls,
                    'drug_a': row.get('source_label_eng', c1),
                    'drug_b': row.get('target_label_eng', c2),
                    'reason': row.get('reason', '-'),
                    'raw_count': row.get('raw_count', 0)
                })

print(f'Double-hit pairs (GC 중복 + AC 금기): {len(double_hit_pairs)}')
if double_hit_pairs:
    df_dh = pd.DataFrame(double_hit_pairs)
    print(df_dh.to_string())

# DC analysis
print('\n\n=== DC (용량주의) ===')
dc = pd.read_csv('data/raw/OpenData_PotOpenDurIngr_DC20260312.csv', encoding='utf-8-sig', low_memory=False)
dc_codes = set(dc['DUR성분코드'].dropna().astype(str))
dc_in_ac = dc_codes & ac_codes
print(f'DC 고유 코드: {len(dc_codes)}, AC와 교집합: {len(dc_in_ac)}')

# How many hub drugs (top degree) are also dose-caution?
node['is_dose_caution'] = node['code'].astype(str).isin(dc_codes)
top_hubs = node.nlargest(20, 'degree')[['label_eng', 'degree', 'is_dose_caution']]
print('\n상위 20 허브 중 용량주의 해당:')
print(top_hubs.to_string())

# GC class -> how many of its drugs appear in AC graph
print('\n\n=== GC 계열별 AC 그래프 내 비율 ===')
rows = []
for cls, codes in class_to_codes.items():
    codes_str = [str(c) for c in codes]
    in_ac = sum(1 for c in codes_str if c in ac_codes)
    rows.append({'class': cls, 'total': len(codes_str), 'in_ac': in_ac, 'pct': round(in_ac/len(codes_str)*100)})
df_gc = pd.DataFrame(rows).sort_values('in_ac', ascending=False)
print(df_gc.head(20).to_string())
