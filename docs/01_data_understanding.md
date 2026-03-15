# Data Understanding

## Dataset Files
- AC: co-administration contraindications.
- BC: age-specific contraindications.
- CC: pregnancy contraindications.
- DC: dosage cautions.
- EC: treatment duration cautions.
- FC: elderly cautions.
- GC: therapeutic duplication or overlapping efficacy group cautions.
- IC: excipient-related cautions.

## Shared Schema Pattern
The AC, CC, and DC files share a common base structure. Key columns observed in these files include:

- `DUR일련번호`: record identifier.
- `DUR유형`: DUR rule type.
- `단일복합구분코드`: whether the ingredient entry is single-ingredient or combination-based.
- `DUR성분코드`: primary DUR ingredient code.
- `DUR성분명영문`: primary ingredient name in English.
- `DUR성분명`: primary ingredient name in Korean.
- `복합제`: combination ingredient information when relevant.
- `관계성분`: linked raw ingredient descriptors.
- `약효분류코드`: drug efficacy classification code.
- `효능군`: efficacy group.
- `고시일자`: notice or publication date for the rule.
- `금기내용`: rule description or reason text.
- `제형`: dosage form.
- `연령기준`: age threshold when applicable.
- `최대투여기간`: maximum administration period when applicable.
- `1일최대용량`: maximum daily dose when applicable.
- `등급`: rule grade when the dataset provides one.
- `상태`: record status.

Some pair-related columns also appear across files, but they are mainly meaningful for the contraindication dataset:

- `병용금기DUR성분코드`
- `병용금기DUR성분영문명`
- `병용금기DUR성분명`

## AC File Interpretation
The AC file represents pairwise contraindication relationships. A single row means that the primary ingredient and the paired contraindicated ingredient should not be used together, with `금기내용` describing the reason.

From the sample rows:

- One row links Paroxetine to Selegiline hydrochloride with a serotonin syndrome warning.
- One row links Atorvastatin to Ketoconazole with a myopathy warning.
- Combination entries also exist, so edge generation must handle both single and combination products carefully.

Current project interpretation:

- AC is the main source for graph edges.
- The natural first graph model is an ingredient-to-ingredient undirected network.
- Duplicate pairs such as A-B and B-A should be normalized into a canonical edge representation.
- `금기내용` should be retained as edge metadata rather than dropped during deduplication.

## CC File Interpretation
The CC file represents pregnancy contraindication rules at the ingredient level.

From the sample rows:

- The rule type is `임부금기`.
- A `등급` value is present, such as grade 2.
- `금기내용` contains narrative safety statements rather than pairwise relationship logic.

Current project interpretation:

- CC is better modeled as node-level metadata, not as edges.
- Pregnancy grade and warning text can be shown as filters, badges, or detail panel attributes.

## DC File Interpretation
The DC file represents dosage caution rules.

From the sample rows:

- The rule type is `용량주의`.
- `1일최대용량` is the core field for many rows.
- `금기내용` may be empty, while the dosage limit still carries the important rule.

Current project interpretation:

- DC is also better modeled as node-level metadata.
- It may become useful later for detailed ingredient inspection rather than for the first network graph.

## Working Assumptions
- AC will be the first dataset used to construct the network.
- BC, CC, DC, EC, and FC are likely better treated as overlays or ingredient attributes.
- GC may later support therapeutic duplication logic, which could be modeled as another edge type.
- IC appears more specialized and may be deferred unless excipient-level analysis becomes a project goal.

## Open Questions
- How often do contraindication pairs appear in both directions, and do their reason texts always match?
- Should combination products be split into ingredient-level nodes or preserved as distinct entities?
- Which columns are reliable enough for public-facing labels: Korean names, English names, or both?