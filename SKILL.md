---
name: physics-lab-report-fastgen
description: Prepare, generate, and verify Chinese university physics lab report DOCX files from a guide, optional template, photos of raw records, and real data. Use for pre-lab or full reports needing table OCR, calculations, formulas, figures, template preservation, or page review.
---

# Physics Lab Report FastGen

Use scripts/workflow.py to turn report production into three repeatable stages. The script handles files and checks; you remain responsible for understanding the guide, writing accurate content, selecting appropriate figures, and inspecting rendered pages.

## Workflow

1. Run prepare once with the guide, template, images, data, requested sections, and scope. Read inventory.json and the extracted text before drafting.
2. Fill the generated report.json using only verified source facts. Keep the requested section order. Do not invent measurements, experimental outcomes, images, or uncertainty values. Mark predicted results as predictions.
3. Run run. It copies the template, builds a separate DOCX, performs structural QA, and creates page previews when LibreOffice and pdftoppm are available. If PDF conversion is unavailable, export the finished DOCX to PDF and pass --pdf.
4. Open every page preview. Check the cover, scope, watermarks, page breaks, formulas, variables and units, figures, captions, and editable tables. Correct defects and rerun. Mark each inspected page pass in review.json, then run finalize.
5. Deliver only after delivery.json reports pass. Include the output file and any real limitations.

~~~powershell
python scripts/workflow.py prepare --workdir work --guide guide.pdf --template template.docx --section "一、实验目的" --section "二、实验原理" --scope "仅前两项，封面不动"
# Complete work/report.json from the inspected source material.
python scripts/workflow.py run --workdir work
python scripts/workflow.py finalize --workdir work
~~~

Prepare never overwrites an existing report.json. Run rejects empty sections and checks that the source template hash is unchanged. The script cannot judge whether a measurement is true or an image has a watermark; those require source review.

Read [references/spec-schema.md](references/spec-schema.md) when writing report JSON. Read [references/workflow.md](references/workflow.md) for renderer setup, review statuses, and old DOC templates.

## Optional data and figure path

When the inputs include a photographed raw-data table, calculation requirements, or requested generated figures, read [references/advanced-workflow.md](references/advanced-workflow.md). Use table_ocr.py to propose cells, compare every cell with the source, and explicitly verify the corrected CSV before analyze_data.py consumes it. Use the experiment's own formulas and uncertainty rules; check units and retain the source and calculation hashes. Use figure_tools.py for reversible image preparation, plots from verified data, and explicitly specified schematic diagrams. Then reference the verified analysis manifest from report.json and inspect every rendered report page.

Keep these optional dependencies off the ordinary text-only report path. Never present an OCR guess, generated schematic, or synthetic image as an observed measurement or photograph.
