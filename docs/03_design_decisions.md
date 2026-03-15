# Design Decisions

## Current Decisions

- The first graph will use AC as the primary edge source.
- The first network model will be ingredient-level, not patient-level.
- Contraindicated pairs will initially be treated as undirected edges.
- Edge metadata should retain the original contraindication reason text.
- CC and DC should be modeled as node attributes or overlay layers rather than graph edges.
- Both Korean and English ingredient names should be preserved during preprocessing.

## Pending Decisions

- How to normalize rows involving combination products.
- How to merge or preserve multiple reason texts for the same canonical pair.
- Whether to use ingredient codes, English names, or bilingual labels as the primary node key in the UI.
- Whether GC should become a second edge type in a later version.

## Decision Rule

When a modeling choice is unclear, prefer the option that preserves source information and can be simplified later without losing traceability.