---
name: tencent_doc_review_native
description: 使用腾讯文档 MCP 下载 Word 文档，在本地生成带审核批注的 Word，再上传回腾讯文档。
metadata:
  openclaw:
    requires:
      bins:
        - tencent-doc-review
---

# Tencent Doc Review Native Skill

当用户希望审阅腾讯文档里的产品调研报告、测评报告、竞品分析报告时，使用这个 skill。

## 适用范围

- 输入是腾讯文档链接或 `doc-id`
- 需要保留 Word 原排版
- 需要输出带 Word 原生评论气泡的 `.docx`
- 需要把审核后的 Word 上传回腾讯文档指定位置或原位置

## 必须遵守的规则

1. 不要在 OpenClaw 内再次调用 `openclaw` CLI 或 `tencent-doc-review skill-run`
2. 审核本地 Word 时只调用：

```bash
tencent-doc-review review-docx --input-docx "<本地docx路径>" --title "<文档标题>"
```

3. 如果用户明确指定模型，再传 `--provider deepseek` 或 `--provider minimax`
4. 如果用户要求“上传回原位置”：
   - 必须先通过腾讯文档 MCP 获取原文档所在的空间 / 文件夹 / 路径信息
   - 在执行上传前，必须先把已解析到的原位置明确成一句可验证的话，例如“acemode团队空间 / 调研团队”
   - 如果无法可靠确定原位置，必须向用户确认
   - 不允许擅自默认上传到“更改”或其他固定文件夹
5. 如果用户提供的是 `https://docs.qq.com/space/...?...resourceId=...` 链接：
   - 需要把它识别成“团队空间 / 空间视图中的文档引用”
   - 优先使用 `resourceId` 作为目标文档节点标识
   - 必要时结合空间上下文确认真实文档对象
6. 如果本地 CLI 检测到 `LLM_API_KEY` 缺失或质量评分异常低：
   - 必须明确告诉用户本次审核未真正完成
   - 不要把空批注文件当成成功审核结果
7. 如果本地 `review-docx` 命令报“Downloaded source document appears incomplete”或正文内容明显只有一句话：
   - 必须停止，不允许上传
   - 这通常意味着 team space 链接被错误解析成了空对象或错误资源
8. 整个流程只允许最终上传一次：
   - 不允许先上传占位版、空文档或中间版本
   - 只有在本地审核命令成功返回且结果可信时，才能上传最终 `upload_candidate_path`

## 标准工作流

1. 用腾讯文档 MCP 下载目标文档为 `.docx`
2. 运行本地审核命令：

```bash
tencent-doc-review review-docx --input-docx "<本地docx路径>" --title "<文档标题>"
```

3. 读取命令返回的 JSON，重点关注：
   - `annotated_word_path`
   - `upload_candidate_path`
   - `markdown_report_path`
   - `review_summary`
4. 如果用户要求“原位置”：
   - 先获取源文档的原始空间 / 文件夹信息
   - 再把 `upload_candidate_path` 上传回同一位置
   - 如果无法验证原位置，就停止并追问，不要猜
5. 如果用户要求“指定位置”：
   - 上传到用户明确给出的团队空间 / 文件夹 / 路径
6. 回复用户：
   - 新文档链接
   - 上传位置
   - 审核摘要
   - 如有失败或降级，明确说明原因

## 输出规则

- 默认上传 `upload_candidate_path`
- 如果文件过大被自动压缩，`upload_candidate_path` 会指向压缩版
- Markdown 报告只是附加产物，不替代批注版 Word
- 如果本次审核没有真正跑起 LLM，不应宣称“审核完成”，而应标记为“仅生成了占位产物”

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

- 如果本地命令失败，先把 stderr 摘要告诉用户，再停止
- 如果腾讯文档下载失败，先确认 MCP 登录态、文档权限，以及链接是 `doc/` 还是 `space/...resourceId=...`
- 如果上传失败，优先检查目标空间权限、文件夹权限和文件大小限制
- 如果用户要求“上传回原位置”但最终上传位置与你解析到的原位置不一致，视为失败，不要继续执行
