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
python scripts/workflow.py preflight --mode core
python scripts/workflow.py prepare --workdir work --guide "实验指导书.pdf" --template "报告模板.docx" --section "一、实验目的" --scope "仅完成第一项，封面不动"
# 依据材料填写 work/report.json；需要计算时填入 analysis_plan。
python scripts/workflow.py run --workdir work
# 检查 work/review.json 的 changed_pages，并标记已检查页面。
python scripts/workflow.py finalize --workdir work
~~~

没有自动渲染时，从生成的 DOCX 导出 PDF，然后运行 `python scripts/workflow.py preview --workdir work --pdf "报告.pdf"`，无需再次构建 Word。

重复使用同一模板时，可先用 `template_profile.py create` 建立模板画像，再在 `prepare` 中传入 `--profile`。资料提取、数据分析、拟合图、DOCX 构建及页面预览均按内容哈希复用；只有发生变化的页面需要重新确认。若只是替换一段文字、单元格或已有图片，可用 `docx_patch.py` 定点修改，避免重建整份报告。详见 [快速增量流程](references/fast-workflow.md)。

记录表照片先运行 `table_ocr.py extract`，逐格核对并修正 CSV，再运行 `verify`。在 `report.json` 中引用 `analysis_plan` 和图表的 `fit_id` 后，`run` 会自动完成分析、拟合图和结果填充。详见 [进阶流程](references/advanced-workflow.md)。

[快速增量流程](references/fast-workflow.md) · [报告 JSON 格式](references/spec-schema.md) · [渲染与复核](references/workflow.md) · [开源设计参考](references/research-notes.md)

测试：`python -m unittest discover -s tests -v`。许可证：MIT。
