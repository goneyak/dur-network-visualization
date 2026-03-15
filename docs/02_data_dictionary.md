# Data Dictionary

## Shared Columns

| Column | Meaning | Most Relevant Files | Planned Use |
| --- | --- | --- | --- |
| `DUR일련번호` | Record identifier | All files | Keep for traceability |
| `DUR유형` | DUR rule type | All files | Use to confirm dataset semantics |
| `단일복합구분코드` | Single vs combination indicator | All files | Use during normalization |
| `DUR성분코드` | Primary ingredient code | All files | Core node identifier candidate |
| `DUR성분명영문` | Primary ingredient name in English | All files | Use for English-facing labels |
| `DUR성분명` | Primary ingredient name in Korean | All files | Keep for bilingual display |
| `복합제` | Combination product component info | Combination rows | Use when handling mixed rows |
| `관계성분` | Related raw ingredient descriptors | All files | Keep as supporting source detail |
| `약효분류코드` | Drug efficacy classification code | Many files | Optional grouping/filtering |
| `효능군` | Efficacy group | Some files | Optional grouping/filtering |
| `고시일자` | Rule notice date | All files | Keep as metadata |
| `금기내용` | Warning or rule description | All files | Keep as edge or node detail text |
| `제형` | Dosage form | Many files | Use as supplemental attribute |
| `연령기준` | Age threshold | BC and related files | Use for age-related overlays |
| `최대투여기간` | Maximum administration period | EC and related files | Use later if duration rules are included |
| `1일최대용량` | Maximum daily dose | DC | Use for dosage caution detail view |
| `등급` | Rule grade | CC and similar files | Use as badge/filter metadata |
| `상태` | Record status | All files | Use to exclude inactive rows if needed |

## Pair-Specific Columns

| Column | Meaning | Most Relevant Files | Planned Use |
| --- | --- | --- | --- |
| `병용금기단일복합구분코드` | Paired ingredient single/combination flag | AC | Use during edge normalization |
| `병용금기DUR성분코드` | Paired contraindicated ingredient code | AC | Second node identifier |
| `병용금기DUR성분영문명` | Paired ingredient English name | AC | Edge endpoint label |
| `병용금기DUR성분명` | Paired ingredient Korean name | AC | Edge endpoint label |
| `병용금기복합제` | Paired combination component info | AC | Preserve for complex rows |
| `병용금기관계성분` | Paired raw ingredient descriptors | AC | Preserve as source detail |
| `병용금기약효분류` | Paired efficacy classification | AC | Optional attribute |

## Notes
- The exact column usage should be refined after profiling null rates and duplicate patterns.
- English and Korean ingredient names should both be preserved until the UI labeling strategy is finalized.