# 多格式资料解析

`material_ingest.py` 是可脱离 Skill 使用的本地 CLI。它把课程资料转换为统一材料包：

- `content.md`：按 PDF 页、PPT 幻灯片、Excel 工作表或 Word 段落组织的文本；
- `tables/*.csv`：从 Word、PPT、Excel、CSV 或 TSV 得到的可编辑表格；
- `assets/`：源文件内嵌图片的原始副本；
- `material.json`：源文件哈希、来源位置、表格、图片和是否需要 OCR 的清单。

支持 PDF、DOCX、PPTX、XLSX、CSV、TSV、TXT、Markdown 和常见图片。旧版 DOC、PPT、XLS 先另存为新版 Office 格式。解析完全在本机进行，不上传课程资料。

~~~powershell
python scripts/labfast.py ingest --input "实验1.pptx" --output-dir work/materials/experiment-1
~~~

同一文件再次运行时会核对源文件和全部输出文件哈希，内容未变则直接返回缓存。加 `--force` 可重新生成。`workflow prepare` 已自动调用该功能，通常只在单独检查或导出某份资料时直接运行。

默认 `--backend fast` 使用轻量解析器。扫描版 PDF、复杂多栏页面或含公式区域的图片可安装 `requirements-complex.txt` 后显式运行：

~~~powershell
python scripts/labfast.py preflight --mode complex
python scripts/labfast.py ingest --input "扫描讲义.pdf" --output-dir work/materials/scan --backend docling
~~~

`--backend auto` 只在 Docling 已安装且输入为 PDF 或图片时选择复杂后端，否则继续使用快速后端。复杂后端输出 Markdown 和 `docling.json`，仍需核对表格、公式和阅读顺序。

`material.json` 的 `needs_ocr` 为 `true` 时，说明输入是图片，或 PDF 几乎没有可提取文字。记录表图片走 `labfast.py ocr extract`；复杂扫描讲义可先用可靠 OCR 工具生成带文字层的 PDF，再重新解析。解析出的表格和图片仍需结合原页核对图意、单位、水印及读数。
