# Report JSON schema

The builder reads UTF-8 JSON. Figure paths are resolved relative to the JSON file.

## Root fields

- **title**: Used when no Word template is supplied.
- **metadata**: Key/value data for a generated cover and template placeholders.
- **fields**: Additional placeholders. A key 姓名 replaces {{姓名}}.
- **settings**: Fonts, sizes, spacing, margins, and default image width.
- **sections**: Ordered report sections.

## Section

~~~json
{"title": "二、实验原理", "anchor": "二、实验原理", "blocks": []}
~~~

When anchor exists in the template, blocks are inserted after it. If absent, a new heading is appended. A marker such as {{SECTION:principle}} is replaced by title.

## Paragraph

~~~json
{"type": "paragraph", "text": "普通正文，默认首行缩进两个字符。"}
~~~

Use segments for symbol styling:

~~~json
{
  "type": "paragraph",
  "segments": [
    {"text": "霍尔电压 "},
    {"text": "U", "italic": true},
    {"text": "H", "subscript": true},
    {"text": " 与磁感应强度成正比。"}
  ]
}
~~~

## Formula

~~~json
{"type": "formula", "text": "U_H = K_H I B", "number": "(1)"}
~~~

The expression is stored as an editable Word math object. Simple U_H, U_{H}, and x^2 tokens become native Word subscript/superscript structures. Complex fractions and matrices are not parsed; format those separately before delivery.

## Figure

~~~json
{"type": "figure", "path": "images/principle.png", "caption": "霍尔效应原理示意图", "width_cm": 14.0}
~~~

Figures are centered and receive sequential captions below the image.

## Table

~~~json
{
  "type": "table",
  "caption": "霍尔电压测量表",
  "columns": ["I/mA", "U_H/mV"],
  "rows": [["0.5", ""], ["1.0", ""]]
}
~~~

The first row is shaded and marked as a repeating header. Rows are kept from splitting across pages.

## Page break

~~~json
{"type": "page_break"}
~~~


## Full workflow

Use scripts/workflow.py prepare to create inventory.json and a blank report.json, scripts/workflow.py run to build and render, then inspect each preview page before scripts/workflow.py finalize. See [workflow.md](workflow.md).

## Verified analysis results

The optional root field analysis_manifest points to analysis.json produced by analyze_data.py. workflow.py verifies the raw CSV, OCR review (when present), config, and residual data before building or finalizing. Scalar placeholders such as {{result.fit.slope.value:.4g}} and {{result.fit.slope.unit}} are expanded from that manifest; the format after the colon uses Python numeric formatting. Keep units and significant figures consistent with the experiment instructions. See [advanced-workflow.md](advanced-workflow.md).
