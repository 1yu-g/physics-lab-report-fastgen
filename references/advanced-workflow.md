# 可选的原始数据与图像工作流

普通预习报告继续使用核心 requirements.txt 和 workflow.py。只有收到记录表照片或需要计算、绘图时才安装相应依赖：

~~~powershell
python -m pip install -r requirements-ocr.txt
python -m pip install -r requirements-analysis.txt
python -m pip install -r requirements-figures.txt
~~~

也可以一次安装 requirements-extended.txt。img2table + RapidOCR 是默认离线 OCR 路线；PaddleOCR/Tesseract 是可选后端，需另行安装。首次运行 OCR 可能下载模型。不要把用户的原始照片、CSV、计算结果或工作目录提交到公开仓库。

## 1. 识别原始记录表

先看原图。必要时用 figure_tools.py preprocess 生成矫正副本；原图不会被覆盖。对副本运行：

~~~powershell
python scripts/table_ocr.py extract --input "记录表.png" --output-dir work/ocr
~~~

输出 table-1.csv、ocr-review.png 和 ocr-review.json。将标号预览与原图逐格对照，纠正数字、负号、小数点、单位和表头；CSV 第一行须为可识别的列名。确认后显式运行：

~~~powershell
python scripts/table_ocr.py verify --manifest work/ocr/ocr-review.json --table-id 1 --note "已与原图逐格核对，并修正两处小数点"
~~~

核对会记录原图和 CSV 哈希。CSV 或原图后来变化时，数据分析会拒绝使用它。识别失败或手写数字含糊时，以原图和用户确认的记录为准，不能猜测。

## 2. 计算与公式

在私人工作目录创建 analysis-plan.json：

~~~json
{
  "input": "ocr/table-1.csv",
  "ocr_review": "ocr/ocr-review.json",
  "units": {"I_mA": "mA", "U_mV": "mV"},
  "operations": [
    {"id": "voltage", "type": "summary", "column": "U_mV", "type_b": 0.01},
    {"id": "fit", "type": "linear_fit", "x": "I_mA", "y": "U_mV"},
    {
      "id": "resistance",
      "type": "formula",
      "expression": "U / I",
      "variables": {
        "U": {"value": 0.1, "uncertainty": 0.001, "unit": "V"},
        "I": {"value": 0.01, "uncertainty": 0.0001, "unit": "A"}
      },
      "output_unit": "ohm"
    }
  ]
}
~~~

~~~powershell
python scripts/analyze_data.py run --config work/analysis-plan.json --output-dir work/analysis
~~~

summary 输出均值、样本标准差、A 类标准不确定度及与指定 B 类**标准不确定度**合成的结果。linear_fit 输出斜率、截距、标准误、R² 和残差 CSV。formula 仅接受显式变量和有限的算术表达式，使用 SymPy 记录符号式、Pint 检查/换算单位、uncertainties 传播输入标准不确定度；如果变量相关，先依据实验要求处理相关性，不要把独立变量模型当成通用答案。B 类不确定度的分布、仪器限差和最终有效数字须按实验指导书确定。

公式变量也可使用 {"from": "fit.slope"} 引用前一步结果。每个结果记录数据、配置和 OCR 核对文件的哈希。

## 3. 图像处理与生成

~~~powershell
python scripts/figure_tools.py preprocess --input "记录表原图.jpg" --output work/clean.png --deskew --grayscale --autocontrast
python scripts/figure_tools.py plot --analysis work/analysis/analysis.json --fit-id fit --output work/figures/fit.png
python scripts/figure_tools.py schematic --spec work/schematic.json --output work/figures/circuit.png
~~~

preprocess 仅做几何与对比度处理，并保留原图和参数记录；不要擦除读数或水印。plot 从经核验的数据生成测量点、拟合线和残差图。schematic 只按提供的组件清单画示意图，不伪装成仪器实拍照。示例：

~~~json
{
  "components": [
    {"type": "source_v", "direction": "up", "label": "电源"},
    {"type": "resistor", "direction": "right", "label": "R"},
    {"type": "capacitor", "direction": "down", "label": "C"}
  ]
}
~~~

支持 resistor、capacitor、inductor、source_v、diode、line、ground。生成的每张图都要目视核对元件连接、坐标轴、单位、图注和含义。

## 4. 与报告连接

在 report.json 根部加入 "analysis_manifest": "analysis/analysis.json"。段落、公式或表格中可使用结果占位符，例如：

~~~text
拟合斜率为 {{result.fit.slope.value:.4g}} {{result.fit.slope.unit}}。
~~~

workflow.py run 将核对分析来源后填入结果，并在最终交付前重新验证数据哈希。报告正文仍需依据讲义解释公式和结果；程序不能替代实验判断。
