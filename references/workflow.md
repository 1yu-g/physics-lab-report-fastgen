# 工作流细节

## 资料清点与写作

`workflow.py prepare` 只在新任务开始时运行一次。可重复传入 `--guide`、`--image` 和 `--data`；使用 `--section` 固定用户指定的范围与顺序。输出 `inventory.json`、`source-text/` 和空白 `report.json`，不会覆盖已有报告草稿。重复执行时，未变化资料会复用 `.cache/extract/` 中的提取结果。工作目录可能包含私人资料，不要提交到公开仓库。

脚本不会自动从讲义写正文或判断 PDF 图片是否适合引用。旧版 `.doc` 模板先转为 `.docx`；若 PDF 无法提取文字，先进行 OCR。依据讲义填写章节、公式、图表及单位，避免编造数据。

## 构建与逐页检查

`workflow.py run --workdir work` 一次完成报告构建、结构检查和可用时的页面预览。输出 `output/report.docx`、`output/report.qa.json`、`preview/page-*.png` 和 `review.json`。有 `analysis_plan` 时，同一次运行还计算数据、生成 `fit_id` 图并填入结果。输入内容没有变化时直接复用已有结果；重新渲染后，仅哈希变化的页面重置为 `pending`，未变化且已通过的页面保持 `pass`。

有 LibreOffice 与 Poppler 时自动渲染。若缺少 LibreOffice，从刚生成的 DOCX 在 Word/WPS 导出 PDF，再运行：

~~~powershell
python scripts/workflow.py preview --workdir work --pdf "报告.pdf"
~~~

`preview` 只为现有 DOCX 生成页面图，不重建 Word；PDF 必须对应当前 DOCX。若缺少 `pdftoppm`，安装 Poppler 后再生成页面图。检查每页封面、范围、断页、图表位置、水印、题注、上下标、单位和缩进；确实检查过的页面才在 `review.json` 中标记 `pass`。之后运行 `workflow.py finalize --workdir work`。结构检查不能替代目视复核。
