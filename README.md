# Physics Lab Report FastGen

从实验指导书、模板、图片和真实数据生成中文大学物理实验报告的 Codex Skill。保留原模板，另存 DOCX；报告内容由源材料决定，脚本负责清点、组装、计算和检查。

## 安装

需要 Python 3.10+。普通报告安装 `requirements.txt`；涉及照片识别、数据计算或电路图时，按需安装 `requirements-ocr.txt`、`requirements-analysis.txt` 或 `requirements-figures.txt`，也可一次安装 `requirements-extended.txt`。页面预览需要 LibreOffice 与 Poppler；也可手动从 Word 导出 PDF。

~~~powershell
git clone https://github.com/1yu-g/physics-lab-report-fastgen.git
cd physics-lab-report-fastgen
python -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File scripts/install_skill.ps1
~~~

已有安装运行 `powershell -ExecutionPolicy Bypass -File scripts/install_skill.ps1 -Update`。

## 最短工作流

~~~powershell
python scripts/workflow.py prepare --workdir work --guide "实验指导书.pdf" --template "报告模板.docx" --section "一、实验目的" --scope "仅完成第一项，封面不动"
# 依据材料填写 work/report.json；需要计算时填入 analysis_plan。
python scripts/workflow.py run --workdir work
# 逐页检查 work/preview/page-*.png，并在 work/review.json 标记已检查页面。
python scripts/workflow.py finalize --workdir work
~~~

没有自动渲染时，从生成的 DOCX 导出 PDF，然后运行 `python scripts/workflow.py preview --workdir work --pdf "报告.pdf"`，无需再次构建 Word。

记录表照片先运行 `table_ocr.py extract`，逐格核对并修正 CSV，再运行 `verify`。在 `report.json` 中引用 `analysis_plan` 和图表的 `fit_id` 后，`run` 会自动完成分析、拟合图和结果填充。详见 [进阶流程](references/advanced-workflow.md)。

[报告 JSON 格式](references/spec-schema.md) · [渲染与复核](references/workflow.md) · [开源设计参考](references/research-notes.md)

测试：`python -m unittest discover -s tests -v`。许可证：MIT。
