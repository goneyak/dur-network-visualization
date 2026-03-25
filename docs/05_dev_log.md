# Development Log

## 2026-03-13
- Created the project documentation workspace under `docs/`.
- Reorganized the raw DUR CSV files into `data/raw/`.
- Added the initial project brief, data understanding notes, data dictionary, design decisions, and todo files.

Next:
- Define the AC edge schema.
- Create a first exploration notebook.

# Dev Log

## Backfilled summary
- Explored the AC contraindication dataset and confirmed that repeated ingredient pairs exist in raw rows.
- Verified that the raw AC file should not be used directly as graph edges.
- Built a canonical pair-based contraindication edge table (`edge_df`).
- Built a node table (`node_df`) and calculated degree for each ingredient.
- Added BC, CC, and FC overlays to create `node_overlay_df`.
- Built a NetworkX graph from edge and node tables.
- Generated static and interactive ego-network visualizations for selected hub ingredients.
- Converted the notebook pipeline into a Streamlit MVP.

## 2026-03-15

### What I did
- Finalized the README.
- Saved app screenshots.
- Built a Streamlit prototype with a drug selector, summary cards, interactive ego-network view, and neighbor table.

### What I learned
- Ego-network visualization is a practical first interface for public DUR graph exploration.
- Degree is useful for identifying hub ingredients, but it should not be interpreted as absolute clinical risk.
- Overlay metadata makes the graph easier to interpret.

### Next step
- Verify the app runs cleanly from a fresh environment.
- Push the project to GitHub.
- Decide whether to add GC overlay or UI filters next.