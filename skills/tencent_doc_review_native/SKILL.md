---
name: tencent_doc_review_native
description: 使用腾讯文档 MCP 下载 Word 文档，在本地生成带审核批注的 Word，并再上传回腾讯文档。
metadata:
  openclaw:
    requires:
      bins:
        - tencent-doc-review
---

# Tencent Doc Review Native Skill

当用户希望审核腾讯文档里的产品调研报告、测评报告、竞品分析报告时，使用这个 skill。

## 适用范围

- 输入是腾讯文档链接或 `doc-id`
- 需要保留 Word 原排版
- 需要输出带原生 Word 评论气泡的 `.docx`
- 需要把审核后的 Word 再上传到腾讯文档指定位置

## 不要做的事

- 不要在 OpenClaw 内再次调用 `openclaw` CLI 或 `tencent-doc-review skill-run`
- 不要上传原始下载文件
- 不要把找不到锚点的批注挂到正文最后一段

## 标准工作流

1. 使用腾讯文档 MCP 下载目标文档为 `.docx` 到当前工作区的 `downloads/` 或用户指定目录。
2. 运行本地审核命令：

```bash
tencent-doc-review review-docx --input-docx "<本地docx路径>" --title "<文档标题>"
```

如果用户明确指定模型，再补 `--provider deepseek` 或 `--provider minimax`。

3. 读取命令返回的 JSON，重点关注：
   - `annotated_word_path`
   - `upload_candidate_path`
   - `markdown_report_path`
   - `review_summary`
4. 使用腾讯文档 MCP 将 `upload_candidate_path` 上传到用户指定的位置。
5. 回复用户：
   - 新文档链接
   - 本地批注版路径
   - 审核摘要

## 输出规则

- 默认上传 `upload_candidate_path`
- 如果文件过大被自动压缩，`upload_candidate_path` 会指向压缩版
- Markdown 报告只作为附加产物，不替代批注版 Word

## 命令返回示例

```json
{
  "source_path": "E:/repo/downloads/demo.docx",
  "annotated_word_path": "E:/repo/downloads/demo-annotated.docx",
  "upload_candidate_path": "E:/repo/downloads/demo-annotated-compressed.docx",
  "markdown_report_path": "E:/repo/downloads/demo-annotated.review.md",
  "annotation_count": 8,
  "review_issue_count": 8,
  "review_summary": "Quality score 82.0/100 ..."
}
```

## 失败处理

- 如果本地命令失败，先把 stderr 摘要告诉用户，再停止，不要盲目重试上传。
- 如果腾讯文档下载失败，先确认 MCP 登录态和文档权限。
- 如果上传失败，优先检查目标文件夹权限和文件大小限制。
