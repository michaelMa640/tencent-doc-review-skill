# 腾讯文档 MCP 在 Claude Code（macOS）中的配置说明

## 结论

腾讯文档这个 MCP 不是只能搭配 OpenClaw 使用。

腾讯官方资料里实际上给了两类接入方式：

- `CodeBuddy / 其他 IDE`：直接把远程 MCP 服务接入客户端
- `OpenClaw`：通过 `setup.sh` 和 `mcporter` 走 skill 注册流程

虽然腾讯官方页面没有单独点名 `Claude Code`，但结合 Claude Code 官方已经支持远程 `HTTP MCP` 和自定义请求头，可以判断 Claude Code 在 macOS 环境下可以直接接入腾讯文档 MCP。

## Claude Code 下的推荐配置

### 1. 先获取腾讯文档 MCP Token

到腾讯文档 MCP 管理页获取 Token：

- <https://docs.qq.com/open/auth/mcp.html>

### 2. 在 macOS 终端中执行

```bash
claude mcp add --transport http --scope user \
  --header "Authorization: 你的Token" \
  tencent-docs https://docs.qq.com/openapi/mcp
```

这条命令会把腾讯文档 MCP 以用户级配置加入 Claude Code。

### 3. 检查是否添加成功

```bash
claude mcp list
claude mcp get tencent-docs
```

进入 Claude Code 后，也可以使用：

```text
/mcp
```

查看连接状态。

## 关键注意事项

### Header 必须这样写

- Header 名必须是 `Authorization`
- 按腾讯文档示例，值直接填你的 Token
- 不要随意改成别的 header 名

### 常见报错

- `400006`：通常是 Token 不对，或者 `Authorization` header 配置错误
- `400007`：通常是账号权限或会员能力不足

## 为什么它不只支持 OpenClaw

OpenClaw 只是腾讯官方提供的另一条接入路径，适合走它自己的 skill 安装流程。

如果你的客户端本身已经支持标准 MCP 协议，尤其是远程 `HTTP MCP` 与自定义 header，那么就没有必要必须走 OpenClaw。这也是 Claude Code 可以直接接入的原因。

## 如果已经配置过 Claude Desktop

如果你已经先在 Claude Desktop 中配置好了 MCP，Claude Code 官方也支持直接导入：

```bash
claude mcp add-from-claude-desktop
```

## 参考资料

- 腾讯文档 MCP 概述：<https://docs.qq.com/open/document/mcp/>
- 腾讯云上的腾讯文档 MCP 使用指南：<https://cloud.tencent.com/developer/mcp/server/11803>
- Claude Code 官方 MCP 文档：<https://docs.anthropic.com/en/docs/claude-code/mcp>

