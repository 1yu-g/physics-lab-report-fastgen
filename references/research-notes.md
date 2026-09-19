# Design research notes

The project uses independently written code. These public repositories informed its design:

- [experiment-report-skill](https://github.com/lyf94697-droid/experiment-report-skill): copy-first templates, content-first assembly, and fast/strict QA.
- [md2docx-math](https://github.com/advancehs/md2docx-math): Word-native math is preferable to raw LaTeX in DOCX files.
- [format-agent-skill](https://github.com/KaguraNanaga/format-agent-skill): deterministic formatting and explicit validation are more reliable than repeated GUI edits.
- [academic-word-codex-skill](https://github.com/dongtingshuo/academic-word-codex-skill): use real Word structures and render final pages before claiming submission readiness.

FastGen deliberately keeps a smaller scope: one JSON contract, one Python builder, and structural QA. It does not bundle school branding, scrape report examples, fabricate data, or require a multi-agent workflow.

## Optional measurement and image tools

- [img2table](https://github.com/xavctn/img2table) (MIT): bordered/borderless table geometry from images and PDFs; optional OCR adapters.
- [RapidOCR](https://github.com/RapidAI/RapidOCR) (Apache-2.0): offline Chinese/English OCR backend. OCR is proposed data, never an accepted measurement until visual review.
- [PaddleOCR PP-StructureV3](https://github.com/PaddlePaddle/PaddleOCR) (Apache-2.0): optional heavier fallback for complex layouts and formula regions.
- [pandas](https://github.com/pandas-dev/pandas), [SciPy](https://github.com/scipy/scipy), [SymPy](https://github.com/sympy/sympy), [Pint](https://github.com/hgrecco/pint), and [uncertainties](https://github.com/lmfit/uncertainties): tabular analysis, fitting, symbolic expressions, units, and error propagation.
- [Matplotlib](https://github.com/matplotlib/matplotlib), [OpenCV](https://github.com/opencv/opencv), and [Schemdraw](https://github.com/cdelker/schemdraw): reproducible plots, photo geometry and contrast processing, and explicit schematic diagrams.
- [lab-report-craft](https://github.com/Rtiming/lab-report-craft) (MIT): numerical provenance and figure-review gates informed the optional workflow. Its LaTeX pipeline was not copied into this DOCX project.

The project depends on upstream packages and links to their repositories; it does not vendor their code or model weights. Install optional packages only for tasks that need them, and keep actual student/course materials out of the public repository.
