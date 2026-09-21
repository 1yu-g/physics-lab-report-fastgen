# 原始数据与图像

普通报告只需核心依赖。照片 OCR 安装 `requirements-ocr.txt`；数据计算与拟合图安装 `requirements-analysis.txt`；电路示意图另需 `requirements-figures.txt`。也可安装 `requirements-extended.txt`。默认 OCR 使用 img2table + RapidOCR；首次使用可能下载模型。PaddleOCR/Tesseract 是另装的可选后端。

## 记录表照片

先检查原图。必要时用 `figure_tools.py preprocess` 生成旋转、裁剪或对比度调整后的副本；原图不覆盖。识别、核对分开进行：

~~~powershell
python scripts/labfast.py ocr extract --input "记录表.png" --output-dir work/ocr
# 对照原图和 ocr-review.png 逐格纠正 work/ocr/table-1.csv 后：
python scripts/labfast.py ocr verify --manifest work/ocr/ocr-review.json --table-id 1 --note "逐格核对并修正读数"
~~~

CSV 首行应是列名。核对数字、符号、小数点、表头和单位；模糊读数不能猜测。相同原图和参数再次运行 `extract` 会直接复用结果，避免重新加载 OCR 模型；确需重新识别时加 `--force`。`verify` 会在清单中记录相对 OCR 原值发生变化的单元格。识别结果在明确核对前不可用于计算，原图或已验证 CSV 变化后需重新核对。

常用的均值和线性拟合计划可以直接生成，再补充本实验特有的公式：

~~~powershell
python scripts/labfast.py data plan --input work/ocr/table-1.csv --ocr-review work/ocr/ocr-review.json --output work/analysis-plan.json --summary U_mV --type-b U_mV=0.02 --x I_mA --y U_mV --unit I_mA=mA --unit U_mV=mV
~~~

## 一次运行分析与绘图

在私人工作目录创建 `analysis-plan.json`，例如：

~~~json
{
  "input": "ocr/table-1.csv",
  "ocr_review": "ocr/ocr-review.json",
  "units": {"I_mA": "mA", "U_mV": "mV"},
  "operations": [
    {"id": "voltage", "type": "summary", "column": "U_mV", "type_b": 0.01},
    {"id": "fit", "type": "linear_fit", "x": "I_mA", "y": "U_mV"},
    {"id": "resistance", "type": "formula", "expression": "U / I",
     "variables": {
       "U": {"value": 0.1, "uncertainty": 0.001, "unit": "V"},
       "I": {"value": 0.01, "uncertainty": 0.0001, "unit": "A"}
     }, "output_unit": "ohm"}
  ]
}
~~~

在 `report.json` 根部写 `"analysis_plan": "analysis-plan.json"`，在需要拟合图的章节放入：

~~~json
{"type": "figure", "fit_id": "fit", "caption": "测量数据拟合与残差图"}
~~~

正文可写 `{{result.fit.slope.value:.4g}} {{result.fit.slope.unit}}`。运行一次 `workflow.py run --workdir work` 会校验 OCR 核对状态、计算结果、生成拟合图并构建报告；结果文件位于 `work/analysis/`，图在 `work/figures/`。已生成的 `analysis.json` 也可用旧字段 `analysis_manifest` 直接引用，但不要与 `analysis_plan` 同时使用。独立脚本 `analyze_data.py` 和 `figure_tools.py` 仍可按需单独运行。

summary 输出均值、样本标准差及 A/B 类合成标准不确定度；linear_fit 输出斜率、截距、标准误、R² 和残差；formula 用符号表达式、单位换算和输入标准不确定度传播。B 类分布、相关性及有效数字应按实验指导书判断。所有结果保留源文件哈希，源数据变化后报告复核会拒绝旧结果。

`figure_tools.py` 也支持按显式组件清单绘制电路示意图。示意图须核对连接含义，不可充当仪器照片；处理图片时不要擦除读数或水印。每张图仍须目视核对坐标轴、单位和题注。
