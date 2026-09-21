# 快速增量流程

## 环境预检

首次使用一个环境时运行一次。普通报告用 `core`，有数据处理或记录表识别时分别用 `analysis`、`ocr`；`full` 检查全部组件。

~~~powershell
python scripts/workflow.py preflight --mode core
~~~

结果中的 `missing_packages` 表示缺失依赖；`render_ready` 表示 LibreOffice 与 Poppler 是否都可用。预检本身不会安装软件。

## 固定模板画像

同一课程模板首次使用时创建一次画像：

~~~powershell
python scripts/template_profile.py create --template "实验报告模板.docx" --output "profiles/大学物理.json"
python scripts/workflow.py prepare --workdir work --template "实验报告模板.docx" --profile "profiles/大学物理.json" --guide "实验指导书.pdf"
~~~

画像记录模板哈希、锚点、占位符、表格、图片和页面设置。模板文件变化后校验会停止，重新创建画像即可，避免把旧定位规则套到新模板。

## 自动缓存

以下步骤都按源文件和配置的 SHA-256 哈希判定，重复运行无需额外参数：

- `prepare`：复用 PDF、DOCX 和文本的提取结果；
- `analyze_data.py`：复用验证过的数据分析清单；
- `figure_tools.py plot-fit`：复用未变化的拟合图；
- `workflow.py run`：复用未变化的 DOCX 和结构检查；
- 页面渲染：DOCX 未变时复用预览，变化后只把内容不同的页面列入 `changed_pages`。

任何输入文件、配置或输出哈希不匹配都会使对应缓存失效。

## 定点修改现有报告

仅修改少量文字、表格单元格或已有图片时，建立补丁 JSON：

~~~json
{
  "source": "霍尔效应实验报告.docx",
  "output": "霍尔效应实验报告-修订.docx",
  "paragraphs": [
    {"find": "旧结论", "replace": "修订后的结论"}
  ],
  "table_cells": [
    {"table": 1, "row": 2, "column": 4, "text": "6.62"}
  ],
  "images": [
    {"index": 2, "path": "新原始数据表.jpg"}
  ]
}
~~~

~~~powershell
python scripts/docx_patch.py --spec patch.json
~~~

表格和图片编号从 0 开始。图片替换保持原位置和尺寸，替换文件必须与原嵌入图片扩展名相同。脚本始终另存输出文件，并检查原文件哈希、DOCX 包完整性以及表格和图片数量。补丁完成后仍需用 `workflow.py preview` 生成页面图并目视复核。
