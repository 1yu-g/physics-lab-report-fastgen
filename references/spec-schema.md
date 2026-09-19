# Report JSON schema

The builder reads UTF-8 JSON. Figure paths are resolved relative to the JSON file.

## Root fields

- **title**: Used when no Word template is supplied.
- **metadata**: Key/value data for a generated cover and template placeholders.
- **fields**: Additional placeholders. A key 姓名 replaces {{姓名}}.
- **settings**: Fonts, sizes, spacing, margins, and default image width.
- **sections**: Ordered report sections.
- **analysis_plan** (optional): Relative path to a data-analysis plan; `run` computes and links results.
- **analysis_manifest** (optional): Existing analysis result; mutually exclusive with `analysis_plan`.

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


## Analysis and generated fit figures

The optional root field `analysis_plan` points to an analysis-plan.json file. `workflow.py run` then computes verified results and writes `work/analysis/analysis.json`. A figure block with `fit_id` instead of `path` generates a fit/residual plot from the named linear-fit result:

~~~json
{"type": "figure", "fit_id": "fit", "caption": "拟合与残差图"}
~~~

Scalar placeholders such as `{{result.fit.slope.value:.4g}}` and `{{result.fit.slope.unit}}` are filled from the analysis. The format after the colon uses Python numeric formatting. For an analysis already run separately, use the legacy `analysis_manifest` root field instead of `analysis_plan`. See [advanced-workflow.md](advanced-workflow.md) for the data plan and review gate.
