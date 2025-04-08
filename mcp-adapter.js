#!/usr/bin/env node

/**
 * MCP适配器 - ThreeJS控制
 * 
 * 用于处理MCP命令并执行ThreeJS相关操作，遵循标准MCP协议
 */

const fs = require('fs');
const path = require('path');

// 处理命令行参数
const args = process.argv.slice(2);
let action = '';
let params = {};

// 解析命令行参数
for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--action' && i + 1 < args.length) {
        action = args[i + 1];
        i++;
    } else if (arg === '--params' && i + 1 < args.length) {
        try {
            params = JSON.parse(args[i + 1]);
        } catch (e) {
            console.error('无法解析参数JSON:', e.message);
            process.exit(1);
        }
        i++;
    }
}

// 检查必要参数
if (!action) {
    console.error('缺少必要的--action参数');
    process.exit(1);
}

// 获取环境变量
const SCENE_ID = process.env.THREEJS_SCENE_ID || 'scene_001';
const DEBUG = process.env.MCP_DEBUG === 'true';

// 日志函数
function log(message) {
    if (DEBUG) {
        console.error(`[MCP Debug] ${message}`);
    }
}

log(`开始处理MCP命令: ${action}, 参数: ${JSON.stringify(params)}`);

// 执行MCP命令
async function executeMCPCommand(action, params) {
    // 实际应用中这里会与前端ThreeJS进行通信
    // 这里使用模拟响应，让调用者知道命令已被正确处理
    
    // 常见操作的处理
    switch (action) {
        case 'rotate':
            return handleRotate(params);
        case 'zoom':
            return handleZoom(params);
        case 'focus':
            return handleFocus(params);
        case 'reset':
            return handleReset(params);
        default:
            return handleCustom(action, params);
    }
}

// 处理旋转操作
function handleRotate(params) {
    const { direction = 'left', angle = 45, target = null } = params;
    log(`处理旋转操作: direction=${direction}, angle=${angle}, target=${target}`);
    
    return {
        success: true,
        action: 'rotate',
        parameters: { direction, angle, target },
        result: {
            rotated: true,
            angleApplied: angle,
            directionApplied: direction,
            timestamp: new Date().toISOString()
        }
    };
}

// 处理缩放操作
function handleZoom(params) {
    const { scale = 1.5, target = null } = params;
    log(`处理缩放操作: scale=${scale}, target=${target}`);
    
    return {
        success: true,
        action: 'zoom',
        parameters: { scale, target },
        result: {
            zoomed: true,
            scaleApplied: scale,
            timestamp: new Date().toISOString()
        }
    };
}

// 处理聚焦操作
function handleFocus(params) {
    const { target = 'center' } = params;
    log(`处理聚焦操作: target=${target}`);
    
    return {
        success: true,
        action: 'focus',
        parameters: { target },
        result: {
            focused: true,
            targetApplied: target,
            timestamp: new Date().toISOString()
        }
    };
}

// 处理重置操作
function handleReset(params) {
    log(`处理重置操作`);
    
    return {
        success: true,
        action: 'reset',
        parameters: {},
        result: {
            reset: true,
            timestamp: new Date().toISOString()
        }
    };
}

// 处理自定义操作
function handleCustom(action, params) {
    log(`处理自定义操作: ${action}, 参数: ${JSON.stringify(params)}`);
    
    return {
        success: true,
        action: action,
        parameters: params,
        result: {
            custom: true,
            customAction: action,
            timestamp: new Date().toISOString()
        }
    };
}

// 记录操作日志
function logOperation(action, params, result) {
    if (!DEBUG) return;
    
    const logEntry = {
        timestamp: new Date().toISOString(),
        action,
        params,
        result
    };
    
    try {
        const logDir = path.join(__dirname, 'logs');
        if (!fs.existsSync(logDir)) {
            fs.mkdirSync(logDir, { recursive: true });
        }
        
        const logFile = path.join(logDir, 'mcp-operations.log');
        fs.appendFileSync(logFile, JSON.stringify(logEntry) + '\n');
    } catch (e) {
        console.error('无法写入日志:', e.message);
    }
}

// 主流程
async function main() {
    try {
        // 执行命令
        const result = await executeMCPCommand(action, params);
        
        // 记录操作
        logOperation(action, params, result);
        
        // 输出结果
        console.log(JSON.stringify(result));
        
        // 成功退出
        process.exit(0);
    } catch (error) {
        // 处理错误
        const errorResult = {
            success: false,
            action: action,
            parameters: params,
            error: error.message || '未知错误'
        };
        
        // 记录错误
        logOperation(action, params, errorResult);
        
        // 输出错误
        console.log(JSON.stringify(errorResult));
        
        // 错误退出
        process.exit(1);
    }
}

// 执行主流程
main(); 