# 数字孪生浏览器操作服务 (Digital Twin Browser Service)

这是一个基于FastAPI和Playwright的服务，用于操控3D数字孪生模型。该服务可以接收JSON格式的操作指令或自然语言描述，通过浏览器控制前端的3D模型展示。

## 功能特性

- **WebSocket通信**：支持实时双向通信，执行JavaScript脚本
- **HTTP API**：提供REST风格的API接口
- **多浏览器支持**：支持Chromium、Firefox和WebKit
- **自然语言接口**：通过Dify API将自然语言转换为操作指令
- **健康检查**：提供服务状态监控
- **性能监控**：实时跟踪资源使用和操作效率
- **自动重试**：智能错误恢复机制
- **丰富的测试工具**：综合测试套件

## 安装依赖

```bash
# 安装Python依赖
pip install -r requirements.txt

# 安装Playwright浏览器
python -m playwright install chromium
# 或其他浏览器
# python -m playwright install firefox
# python -m playwright install webkit
```

## 配置说明

服务支持通过环境变量或命令行参数进行配置：

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| 前端URL | FRONTEND_URL | http://localhost:3000 | 3D模型前端页面地址 |
| 浏览器类型 | BROWSER_TYPE | chromium | 可选：chromium, firefox, webkit |
| 无头模式 | HEADLESS | true | 是否启用无头模式 |
| 端口 | PORT | 9000 | 服务监听端口 |
| 日志级别 | LOG_LEVEL | info | 可选：debug, info, warning, error |
| Dify API端点 | DIFY_API_ENDPOINT | - | Dify API服务地址 |
| Dify API密钥 | DIFY_API_KEY | - | Dify API访问密钥 |

## 启动服务

使用启动脚本启动服务：

```bash
# 最简单的启动方式
python start_service.py

# 指定参数启动
python start_service.py --browser firefox --port 9001 --frontend-url http://localhost:3000 --log-level debug
```

或者直接启动服务器：

```bash
python mcp_server.py
```

## API接口说明

### HTTP接口

- `GET /health` - 服务健康检查
- `GET /metrics` - 性能指标监控
- `POST /api/execute` - 执行模型操作
- `POST /api/reinitialize` - 重新初始化浏览器
- `POST /api/llm/process` - 处理自然语言指令（需配置Dify API）

### WebSocket接口

连接到 `ws://localhost:9000/ws`，发送JSON格式消息：

**执行脚本**:
```json
{
  "type": "execute_script",
  "script": "return window.rotateModel(null, 'left', 45);",
  "timestamp": "2023-06-30T12:00:00Z"
}
```

**健康检查**:
```json
{
  "type": "health_check",
  "timestamp": "2023-06-30T12:00:00Z"
}
```

## 支持的模型操作

| 操作 | 说明 | 参数 |
|------|------|------|
| rotate | 旋转模型 | angle, axis |
| zoom | 缩放模型 | scale |
| focus | 聚焦模型 | target |
| reset | 重置模型 | - |
| changeMaterial | 更改材质 | material, color |
| toggleAnimation | 切换动画 | name, enabled |

## 测试工具

运行综合测试：

```bash
# 运行所有测试
python test_comprehensive.py

# 运行特定测试
python test_comprehensive.py health
python test_comprehensive.py api
python test_comprehensive.py websocket
```

## 前端集成

前端需要通过WebSocket连接服务，示例代码：

```javascript
const ws = new WebSocket('ws://localhost:9000/ws');

ws.onopen = () => {
  console.log('WebSocket连接已建立');
};

ws.onmessage = (event) => {
  const response = JSON.parse(event.data);
  console.log('收到消息:', response);
};

// 执行模型操作
function executeScript(script) {
  ws.send(JSON.stringify({
    type: 'execute_script',
    script: script,
    timestamp: new Date().toISOString()
  }));
}

// 示例: 旋转模型
executeScript('return window.rotateModel(null, "left", 45);');
```

## 常见问题排查

1. **服务无法启动**
   - 检查端口是否被占用
   - 确认Playwright是否正确安装
   - 查看日志文件获取详细错误信息

2. **浏览器无法连接到前端**
   - 确认前端服务是否正在运行
   - 检查FRONTEND_URL配置是否正确
   - 尝试使用不同的浏览器类型

3. **操作未生效**
   - 检查前端是否正确实现了相应的全局函数
   - 查看WebSocket响应中的错误信息
   - 使用测试工具验证服务正常运行

## 许可证

MIT