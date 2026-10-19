# Private Condo Market Analysis

An interactive dashboard of Singapore private condominium transactions, served on GitHub Pages. This is the sister project of [hdb-resale-dashboard](https://github.com/garethgoh99/hdb-resale-dashboard).

> **Status:** setup. The data source, pipeline and dashboard haven't been built yet.

## Planned layout

Mirrors the HDB project:

```
pipeline/        fetch → harmonize → aggregate → build
template/        dashboard_template.html
data/            small committed reference data and the refresh log
.github/workflows/  scheduled refresh + GitHub Pages deploy
reference/hdb-skills/  the HDB dashboard skill set, kept as the design reference
```

## Reference

`reference/hdb-skills/` holds the four skills (ingestion, aggregation, map outline, dashboard build) from the HDB dashboard. They're the starting point for this project's design and will be adapted for private-condo data.
