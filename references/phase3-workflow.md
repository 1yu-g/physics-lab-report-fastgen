# 第三阶段工作流

## 一次建立报告项目

`start` 将资料清点、多格式解析和来源草稿合并为一步：

~~~powershell
labfast start --workdir work --guide "讲义.pdf" --template "模板.docx" --image "记录表.jpg" --section "一、实验目的" --section "二、实验原理" --scope "完成前两项，封面不动"
~~~

它生成 `inventory.json`、`report.json` 和 `draft-brief.json`。脚本只把标题匹配到的讲义内容作为来源摘录填入空章节，并标记 `source-extract-needs-rewrite-and-verification`。写作时根据 brief 中的来源哈希、相关表格和图片进行改写、补充公式并核对单位；完成后把 `report.json` 的 `draft_status` 改为 `reviewed`，否则构建命令会拒绝生成 DOCX。已有非空章节默认保留；只有明确需要重建来源草稿时才使用 `--refresh-draft`。

## 浏览器逐页复核

报告渲染后启动本地面板：

~~~powershell
labfast review serve --workdir work --open
~~~

页面只在 `127.0.0.1` 提供。每一页可标记“通过”或“待检查”并填写备注。保存前服务器重新核对 DOCX 与页面图哈希，避免把旧页面状态写入新版报告。全部页面通过后仍需运行 `labfast finalize --workdir work` 生成交付清单。

## 复杂解析与性能记录

普通资料使用快速后端。只有扫描页、复杂表格、公式区域或阅读顺序明显错误时才安装并使用 Docling，避免把重模型加入每次报告流程。

~~~powershell
labfast ingest --input "扫描讲义.pdf" --output-dir work/complex --backend docling
labfast benchmark --input "扫描讲义.pdf" --output-dir work/benchmark --runs 3 --backend fast
~~~

基准输出记录源文件哈希、环境、冷启动时间、缓存平均值与中位数及对应倍率。它用于比较同一资料和环境下的优化效果，不把不同电脑或不同文件的耗时直接混为一谈。
