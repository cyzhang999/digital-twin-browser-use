# MCP协议实现文档

## 1. 概述

MCP (Model Control Protocol) 是一种用于控制3D模型的协议，支持以下功能：

- 旋转模型（Rotate）
- 缩放模型（Zoom）
- 聚焦到模型特定部位（Focus）
- 重置模型视图（Reset）
- 自定义操作（Custom）

该协议支持通过WebSocket和REST API两种方式进行通信，可以实现实时控制和反馈。

## 2. 架构设计

### 2.1 整体架构

```
+------------------+        +--------------------+        +---------------+
|                  |  HTTP  |                    |  JS/WS  |               |
|  Web Frontend    |<------>|  Backend Service   |<------->|  3D Model     |
|  (Vue.js)        |  WS    |  (Python/FastAPI)  |         |  (Three.js)   |
|                  |        |                    |         |               |
+------------------+        +--------------------+        +---------------+
       ^                             ^                           ^
       |                             |                           |
       v                             v                           v
+------------------+        +--------------------+        +---------------+
|                  |        |                    |        |               |
|  MCP Client      |        |  MCP Adapter       |        |  Model API    |
|  (TypeScript)    |        |  (Python)          |        |  (JavaScript) |
|                  |        |                    |        |               |
+------------------+        +--------------------+        +---------------+
```

### 2.2 组件说明

1. **MCP适配器** (`mcp_adapter.py`)
   - 负责处理MCP协议消息
   - 解析命令并执行对应操作
   - 管理WebSocket连接

2. **MCP客户端** (`MCPClient.ts`)
   - 提供WebSocket连接管理
   - 提供命令发送和响应处理
   - 支持自动重连和心跳检测

3. **MCP控制面板** (`MCPControlPanel.vue`)
   - 提供MCP协议操作的UI界面
   - 显示连接状态和操作日志

4. **Python服务** (`main.py`)
   - 提供WebSocket和REST API端点
   - 集成MCP适配器
   - 负责与前端通信

## 3. 协议规范

### 3.1 MCP命令格式

```json
{
  "id": "cmd_12345678",
  "action": "rotate",
  "target": "meeting_room",
  "parameters": {
    "direction": "left",
    "angle": 45
  }
}
```

- `id`: 命令唯一标识符
- `action`: 操作类型（rotate/zoom/focus/reset/custom）
- `target`: 操作目标（可选）
- `parameters`: 操作参数（特定于操作类型）

### 3.2 MCP消息格式

```json
{
  "type": "command",
  "id": "msg_12345678",
  "timestamp": "2023-09-14T12:34:56.789Z",
  "command": {
    "id": "cmd_12345678",
    "action": "rotate",
    "target": "meeting_room",
    "parameters": {
      "direction": "left",
      "angle": 45
    }
  }
}
```

- `type`: 消息类型（command/response/error等）
- `id`: 消息唯一标识符
- `timestamp`: 消息时间戳
- 其他字段根据消息类型而定

### 3.3 常用消息类型

1. **命令消息** (`command`)
   - 用于发送操作命令

2. **响应消息** (`response`)
   - 用于返回命令执行结果

3. **错误消息** (`error`)
   - 用于返回错误信息

4. **初始化消息** (`init`)
   - 用于客户端初始化连接

5. **心跳消息** (`ping`/`pong`)
   - 用于保持连接活跃

## 4. 接口说明

### 4.1 WebSocket接口

- **WebSocket端点**: `/ws/mcp`
- **支持消息类型**: 所有MCP消息类型

### 4.2 REST API接口

- **命令接口**: `/api/mcp/command`
- **自然语言接口**: `/api/mcp/nl-command`

## 5. 使用示例

### 5.1 前端使用示例

```typescript
// 初始化MCP客户端
const mcpClient = getMCPClient({
  serverUrl: 'http://localhost:9000',
  wsUrl: 'ws://localhost:9000/ws/mcp'
});

// 连接服务
mcpClient.connect();

// 执行旋转命令
mcpClient.rotate('left', 45, null, (result) => {
  console.log('旋转结果:', result);
});

// 执行缩放命令
mcpClient.zoom(1.5, null, (result) => {
  console.log('缩放结果:', result);
});
```

### 5.2 自然语言命令示例

可以通过自然语言发送命令，支持以下格式：

- `向左旋转模型45度`
- `放大模型1.5倍`
- `聚焦到会议室区域`
- `重置模型视图`

## 6. 功能扩展

### 6.1 添加新的命令类型

1. 在 `MCPOperationType` 中添加新的操作类型
2. 在 `MCPCommand` 类中添加对应的创建方法
3. 在 `MCPAdapter` 类中注册对应的处理器

### 6.2 增强自然语言处理能力

可以通过以下方式增强自然语言处理能力：

1. 使用更复杂的正则表达式匹配模式
2. 集成NLP库进行语义分析
3. 调用大模型API进行更精确的意图识别

## 7. 测试工具

- `test_mcp.py`: 全面的MCP协议测试脚本
- `test_mcp_simple.py`: 简单的MCP协议测试脚本
- `test_page.html`: MCP协议测试网页

## 8. 故障排除

### 8.1 连接问题

- 检查WebSocket服务端口是否正确
- 确认防火墙设置允许WebSocket连接
- 检查浏览器控制台是否有连接错误

### 8.2 命令执行问题

- 确认MCP适配器已正确设置页面引用
- 检查命令参数是否正确
- 查看服务端日志了解详细错误信息 