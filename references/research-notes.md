# Design research notes

The project uses independently written code. These public repositories informed its design:

- [experiment-report-skill](https://github.com/lyf94697-droid/experiment-report-skill): copy-first templates, content-first assembly, and fast/strict QA.
- [md2docx-math](https://github.com/advancehs/md2docx-math): Word-native math is preferable to raw LaTeX in DOCX files.
- [format-agent-skill](https://github.com/KaguraNanaga/format-agent-skill): deterministic formatting and explicit validation are more reliable than repeated GUI edits.
- [academic-word-codex-skill](https://github.com/dongtingshuo/academic-word-codex-skill): use real Word structures and render final pages before claiming submission readiness.

FastGen deliberately keeps a smaller scope: one JSON contract, one Python builder, and structural QA. It does not bundle school branding, scrape report examples, fabricate data, or require a multi-agent workflow.
