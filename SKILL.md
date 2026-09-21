---
name: physics-lab-report-fastgen
description: Generate and verify Chinese university physics lab reports in DOCX from supplied guides, templates, figures, or real measurements. Use for pre-lab and full reports that need source-grounded writing, optional table OCR/data analysis, and page review.
---

# Physics Lab Report FastGen

1. Read the user's materials and scope once. Run `scripts/workflow.py preflight --mode core` before the first report in an environment, adding `analysis` or `ocr` only when needed. For a new report, run `prepare` once to inventory sources and create `work/report.json`. For a repeatedly used template, create a profile once with `template_profile.py` and pass it to `prepare --profile`; source extraction is content cached. Fill the JSON from the guide and verified records. Preserve the original template and cover, create a separate DOCX, and never invent measurements or observations.
2. Run `scripts/workflow.py run --workdir work` after drafting. Unchanged inputs reuse analysis, plots, DOCX, and rendered pages. For a small correction to an existing report, use `docx_patch.py` rather than rebuilding the whole document. If calculations are needed, set `analysis_plan`; the same run computes results, fills `{{result...}}` fields, and generates figures marked with `fit_id`. For a photographed table, use `table_ocr.py extract`, compare every CSV cell with the source, correct it, and run `verify` before analysis. Read [fast-workflow.md](references/fast-workflow.md) for cache, profiles, and targeted patches; read [advanced-workflow.md](references/advanced-workflow.md) only for OCR and analysis.
3. Inspect every rendered page for scope, cover, watermark, layout, editable tables, figures, captions, mathematical symbols, units, and two-character body indentation. After a rebuild, unchanged pages retain their passed status; inspect the pages listed in `changed_pages`. If automatic rendering is unavailable, export the existing DOCX to PDF and call `scripts/workflow.py preview --workdir work --pdf report.pdf`; this does not rebuild the DOCX. Mark reviewed pages `pass` in `work/review.json`, then run `finalize`.

The script's structural checks cannot verify scientific truth or visual quality. Deliver only when `work/delivery.json` reports `pass`; state any real limitation. Keep private source files and work directories out of public repositories.

Read [spec-schema.md](references/spec-schema.md) when editing report JSON. Read [workflow.md](references/workflow.md) for renderer setup, review status, or old DOC templates.
