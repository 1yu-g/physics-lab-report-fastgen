# 工作流细节

## prepare：一次清点

向 --guide、--image、--data 重复传入多个路径；模板使用 --template。输出 inventory.json、提取出的 source-text/*.txt 和空白 report.json。这些工作文件可能包含课程材料和个人信息，应放在未公开的工作目录；不要提交到公共仓库。

--section 指定确切范围与顺序。未给出时，会尝试从 DOCX 模板识别中文或数字编号标题，但仍需人工核对。脚本不会从讲义自动生成内容，也不会把 PDF 内嵌图片自动判定为可用插图。扫描 PDF 若提取不到文字，需先 OCR；矢量示意图可能需要从 PDF 页面人工裁取无水印图像。

## run：生成与检查

运行前填写 report.json，确保各章节非空，图像路径存在，图题表题齐全。run 会生成：

- output/report.docx：独立报告。
- output/report.qa.json：DOCX 包、章节、占位符、图片和公式的结构检查。
- preview/page-*.png：可渲染时的逐页预览。
- review.json：每页 pending 的复核清单。

模板中的原有图片、公式和 Normal 样式会被保留；工作流检查源模板的 SHA-256 是否改变。仅用 fastgen.py build 不会自动生成页面预览。

默认只自动调用 LibreOffice。没有 LibreOffice 时，从 Word/WPS 手动导出最终 DOCX 对应的 PDF，再运行 run --pdf path.pdf。需要安装 Poppler 的 pdftoppm 才能生成 PNG 页面；没有页面预览时不能完成 finalize。

## review → finalize：逐页交付门槛

打开每一张页面图，核对封面、范围、溢出与断页、图表位置、水印、题注、公式上下标、变量与单位。发现问题应修改报告 JSON，重新运行 run，再检查新预览。检查过的一页在 review.json 中设 status 为 pass，可以把发现和修复写入 notes。全部页面通过后运行 finalize；它还会验证报告自 run 后没有变化。

结构检查无法证明内容真实、图片无水印或排版美观。delivery.json 中的 pass 依赖实际完成的逐页复核，不应机械批量标记页面。
