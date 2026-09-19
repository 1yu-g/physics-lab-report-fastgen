# Physics Lab Report FastGen

一个可重复使用的 Codex Skill 和 Python 工作流，用于从实验指导书、DOCX 模板、图片及真实数据生成中文大学物理实验报告。AI 负责理解材料与撰写内容；脚本负责资料清点、Word 组装、结构检查和逐页复核记录。

## 能做什么

- 一次清点 PDF/DOCX/文本资料，提取文本、章节、图表线索及图片尺寸。
- 按用户指定的章节顺序生成报告骨架；原模板不被覆盖，封面未指定字段不改动。
- 从 JSON 一次写入正文、Word 原生公式及上下标、图片、可编辑表格和图表题注。
- 检查占位符、章节和图表数量；可用 LibreOffice 和 Poppler 时生成逐页 PNG。
- 逐页检查完成前，工作流不会把报告标记为可交付。

脚本不会自动编造实验数据，也不能可靠识别水印或判断图表是否与讲义相符；这些由使用者在选材和逐页检查时确认。

## 安装

需要 Python 3.10+；运行 python -m pip install -r requirements.txt。若希望自动输出 PDF 页面预览，安装 LibreOffice 和 Poppler (pdftoppm) 并加入 PATH。也可以自行从 Word 导出 PDF，再用 --pdf 生成页面预览。

克隆项目并安装为 Codex Skill：

~~~powershell
git clone https://github.com/1yu-g/physics-lab-report-fastgen.git
cd physics-lab-report-fastgen
python -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File scripts/install_skill.ps1
~~~

## 三步工作流

~~~powershell
python scripts/workflow.py prepare --workdir work --guide "实验指导书.pdf" --template "报告模板.docx" --image "原理图.png" --section "一、实验目的" --section "二、实验原理" --scope "只完成前两项，封面不动"
~~~

读取 work/inventory.json 与 work/source-text/，按原始材料填写 work/report.json。prepare 创建的是空骨架，不会代写未经核实的事实，也不会覆盖已有 report.json。

~~~powershell
python scripts/workflow.py run --workdir work
# 若本机没有 LibreOffice，先自行将生成的 DOCX 导出为 PDF，再运行：
python scripts/workflow.py run --workdir work --pdf "已导出的报告.pdf"
~~~

查看 work/output/report.docx、.qa.json 和 work/preview/page-*.png。检查每一页后，把 work/review.json 中对应页面的 status 从 pending 改为 pass；有问题就先修改 JSON 并重新运行。

~~~powershell
python scripts/workflow.py finalize --workdir work
~~~

只有结构检查通过、每页均标记检查通过且 DOCX 自复核后未变化，才会生成 work/delivery.json，状态为 pass。旧版 DOC 模板需要先转换为 DOCX。

## 原始记录表、计算和图像

进阶功能按需安装，不影响普通报告：requirements-ocr.txt 提供表格识别，requirements-analysis.txt 提供统计、拟合、公式与单位计算，requirements-figures.txt 提供电路示意图。也可安装 requirements-extended.txt。已有本地 skill 可用 `pwsh -File scripts/install_skill.ps1 -Update` 更新。

~~~powershell
python scripts/table_ocr.py extract --input "原始记录表.jpg" --output-dir work/ocr
# 对照原图核对并修正 CSV 后：
python scripts/table_ocr.py verify --manifest work/ocr/ocr-review.json --table-id 1 --note "逐格核对并修正"
python scripts/analyze_data.py run --config work/analysis-plan.json --output-dir work/analysis
python scripts/figure_tools.py plot --analysis work/analysis/analysis.json --fit-id fit --output work/fit.png
~~~

分析结果可以通过 report.json 的 analysis_manifest 及结果占位符进入报告；未经核对的 OCR 表格会被拒绝。详细配置、原图预处理和示意图生成命令见 [advanced-workflow.md](references/advanced-workflow.md)。

## JSON 输入

report.json 的每个章节包含 title、可选的 anchor 和有序 blocks。支持 paragraph、formula、figure、table、page_break。变量可用段落 segments 标注斜体及上下标；公式中的 U_H、x^2 或 U_{H} 会形成 Word 原生上下标。详细格式见 [spec-schema.md](references/spec-schema.md)。

需要只使用组装器时，也可直接运行：

~~~powershell
python scripts/fastgen.py init --output report.json
python scripts/fastgen.py build --spec report.json --template template.docx --output output/report.docx
python scripts/fastgen.py check --input output/report.docx --spec report.json
~~~

build 的 .qa.json 只代表结构检查；正式交付仍需逐页视觉检查。公开仓库不包含真实学生资料、学校模板或课程指导书。

## 验证

~~~powershell
python -m unittest discover -s tests -v
~~~

设计参考与原创实现边界见 [research-notes.md](references/research-notes.md)。许可证：MIT。
