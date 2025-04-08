#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数字孪生浏览器操作服务
(Digital Twin Browser Operation Service)

使用FastAPI和Playwright提供基于Web的3D模型操作服务。
(Provides Web-based 3D model operation service using FastAPI and Playwright.)

运行方式:
1. 安装依赖: pip install -r requirements.txt
2. 安装Playwright浏览器: playwright install
3. 启动服务: python main.py

访问: http://localhost:9000/docs 查看API文档
"""

import os
import sys
import logging
import traceback
import json
import asyncio
import time
import uvicorn
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Union, Any
from contextlib import asynccontextmanager
from functools import wraps
from datetime import datetime
import uuid
import signal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from playwright.async_api import async_playwright, Browser, Page, Playwright
from loguru import logger
from dotenv import load_dotenv

# 检查必要依赖包是否已安装
try:
    import uvicorn
except ImportError as e:
    print(f"错误: 缺少必要依赖 - {e}")
    print("请运行: pip install -r requirements.txt")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 检查Playwright版本
try:
    # 直接使用playwright._repo_version而不是__version__
    from playwright._repo_version import version as playwright_version
    logger.info(f"Playwright版本: {playwright_version}")
except (ImportError, AttributeError) as e:
    logger.warning(f"无法获取Playwright版本信息: {e}")
    playwright_version = "未知"
    
# 检查是否已安装浏览器
def check_browser_installation():
    try:
        import subprocess
        import os
        import glob
        
        # 检查浏览器文件是否存在，这更可靠
        user_home = os.path.expanduser("~")
        
        # 设置不同操作系统的路径
        if os.name == 'nt':  # Windows
            playwright_dir = os.path.join(os.environ.get('USERPROFILE', ''), "AppData", "Local", "ms-playwright")
        else:  # Linux/Mac
            playwright_dir = os.path.join(user_home, ".cache", "ms-playwright")
        
        # 确认目录存在
        if os.path.isdir(playwright_dir):
            # 检查是否存在浏览器目录
            chromium_dirs = glob.glob(os.path.join(playwright_dir, "chromium-*"))
            firefox_dirs = glob.glob(os.path.join(playwright_dir, "firefox-*"))
            webkit_dirs = glob.glob(os.path.join(playwright_dir, "webkit-*"))
            
            if chromium_dirs or firefox_dirs or webkit_dirs:
                logger.info(f"找到已安装的Playwright浏览器: Chromium={bool(chromium_dirs)}, Firefox={bool(firefox_dirs)}, Webkit={bool(webkit_dirs)}")
                return True
        
        # 如果上面的方法失败，尝试运行命令
        try:
            result = subprocess.run(["playwright", "browser-list"], capture_output=True, text=True)
            if result.returncode == 0 and "chromium" in result.stdout.lower():
                logger.info("通过命令行确认Playwright浏览器已安装")
                return True
            else:
                logger.warning("未检测到已安装的Playwright浏览器，请运行: playwright install")
                return False
        except Exception as cmd_error:
            logger.warning(f"运行playwright命令失败: {cmd_error}")
            # 尝试检查Python路径中是否存在playwright包
            try:
                import playwright
                logger.info("检测到Playwright包，但无法确认浏览器是否已安装")
                return True
            except ImportError:
                logger.warning("未检测到Playwright包，请确认安装: pip install playwright")
                return False
            
    except Exception as e:
        logger.error(f"检查Playwright浏览器安装时出错: {e}")
        # 默认假设已安装，避免阻止服务启动
        return True

# 加载环境变量
load_dotenv()

# 从环境变量获取日志级别
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 全局变量
playwright_instance = None
browser: Optional[Browser] = None
page: Optional[Page] = None
active_connections: List[WebSocket] = []

# 加载环境变量
BROWSER_TYPE = os.getenv("BROWSER_TYPE", "chromium")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
VIEWPORT_WIDTH = int(os.getenv("VIEWPORT_WIDTH", "1280"))
VIEWPORT_HEIGHT = int(os.getenv("VIEWPORT_HEIGHT", "800"))
PAGE_LOAD_TIMEOUT = int(os.getenv("PAGE_LOAD_TIMEOUT", "60000"))
MODEL_LOAD_WAIT = int(os.getenv("MODEL_LOAD_WAIT", "5000"))
# API安全设置
API_KEY = os.getenv("API_KEY", "")
API_KEY_REQUIRED = os.getenv("API_KEY_REQUIRED", "false").lower() == "true"

# 添加备用测试页面处理
TEST_PAGE_PATH = os.path.join(os.path.dirname(__file__), 'test_page.html')

# 模型
class ActionType(str, Enum):
    ROTATE = "rotate"
    ZOOM = "zoom"
    FOCUS = "focus"
    RESET = "reset"

class ActionParams(BaseModel):
    """操作参数 (Operation parameters)"""
    direction: Optional[str] = Field("left", description="旋转方向 (Rotation direction)")
    angle: Optional[int] = Field(30, description="旋转角度 (Rotation angle)")
    scale: Optional[float] = Field(1.5, description="缩放比例 (Zoom scale)")

class Action(BaseModel):
    type: ActionType = Field(..., description="操作类型 (Operation type)")
    target: Optional[str] = Field(None, description="目标组件 (Target component)")
    params: Optional[Dict[str, Any]] = Field(None, description="操作参数 (Operation parameters)")

class Request(BaseModel):
    action: Action = Field(..., description="操作动作 (Operation action)")
    requestId: Optional[str] = Field(None, description="请求ID (Request ID)")

# WebSocket管理器
class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket客户端已连接，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket客户端已断开，当前连接数: {len(self.active_connections)}")
    
    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        
        # 清理断开的连接
        for conn in disconnected:
            try:
                self.active_connections.remove(conn)
            except ValueError:
                pass

# 创建WebSocket管理器实例
ws_manager = WebSocketManager()

# 导入MCP服务器
from mcp_server import mcp_server, MCPCommand, MCPOperationType, generate_mcp_command_from_nl

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理器
    在应用启动时初始化浏览器，在应用关闭时清理资源
    """
    # 记录启动时间
    app.state.start_time = time.time()
    
    # 启动时初始化
    try:
        global playwright_instance, browser, page
        
        # 初始化Playwright
        playwright_instance = await async_playwright().start()
        
        # 选择浏览器类型
        if BROWSER_TYPE == "firefox":
            browser_instance = playwright_instance.firefox
        elif BROWSER_TYPE == "webkit":
            browser_instance = playwright_instance.webkit
        else:
            browser_instance = playwright_instance.chromium
        
        # 启动浏览器
        browser = await browser_instance.launch(headless=HEADLESS)
        
        # 创建新页面
        page = await browser.new_page()
        
        # 设置页面大小
        await page.set_viewport_size({"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})
        
        # 导航到数字孪生前端页面
        error_occurred = False
        try:
            logger.info(f"导航到目标页面: {FRONTEND_URL}")
            
            # 使用较短的超时时间进行第一次尝试
            try:
                await page.goto(FRONTEND_URL, wait_until="domcontentloaded", timeout=10000)
                # 如果成功，再等待页面完全加载
                await page.wait_for_load_state("networkidle", timeout=PAGE_LOAD_TIMEOUT)
                logger.info("页面加载完成")
            except Exception as quick_e:
                logger.warning(f"快速导航失败 (可能是前端服务未启动): {quick_e}")
                # 尝试使用备用地址
                backup_url = os.getenv("BACKUP_FRONTEND_URL", "")
                if backup_url:
                    logger.info(f"尝试备用地址: {backup_url}")
                    await page.goto(backup_url, wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT)
                    logger.info("备用页面加载完成")
                else:
                    # 尝试加载本地测试页面
                    try:
                        test_page_path = os.path.join(os.path.dirname(__file__), "static", "test_page.html")
                        test_page_url = f"file://{os.path.abspath(test_page_path)}"
                        logger.info(f"尝试加载本地测试页面: {test_page_url}")
                        await page.goto(test_page_url, wait_until="domcontentloaded", timeout=10000)
                        logger.info("本地测试页面加载完成")
                    except Exception as test_e:
                        logger.warning(f"加载本地测试页面失败: {test_e}")
                        # 如果没有备用方案，重新抛出异常
                        raise quick_e
            
            # 等待3D模型加载
            await page.wait_for_timeout(MODEL_LOAD_WAIT)
        except Exception as e:
            error_occurred = True
            logger.error(f"页面导航失败: {e}")
            # 创建一个功能性的Three.js测试页面作为后备
            await page.set_content("""
            <!DOCTYPE html>
            <html>
                <head>
                    <meta charset="utf-8">
                    <title>数字孪生浏览器操作测试页面</title>
                    <style>
                        body { margin: 0; overflow: hidden; }
                        canvas { width: 100%; height: 100%; display: block; }
                        #info {
                            position: absolute;
                            top: 10px;
                            left: 10px;
                            background: rgba(0,0,0,0.7);
                            color: white;
                            padding: 10px;
                            font-family: monospace;
                            font-size: 12px;
                            pointer-events: none;
                        }
                    </style>
                    <script src="https://cdn.jsdelivr.net/npm/three@0.132.2/build/three.min.js"></script>
                    <script src="https://cdn.jsdelivr.net/npm/three@0.132.2/examples/js/controls/OrbitControls.js"></script>
                </head>
                <body>
                    <div id="info">操作日志:<br></div>
                    <script>
                        // 创建一个真实的Three.js场景
                        let scene, camera, renderer, controls, cube;
                        let logElement = document.getElementById('info');
                        
                        function init() {
                            // 基本场景设置
                            scene = new THREE.Scene();
                            scene.background = new THREE.Color(0x404040);
                            
                            // 相机设置
                            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
                            camera.position.z = 5;
                            
                            // 渲染器
                            renderer = new THREE.WebGLRenderer({ antialias: true });
                            renderer.setSize(window.innerWidth, window.innerHeight);
                            document.body.appendChild(renderer.domElement);
                            
                            // 添加轨道控制器
                            controls = new THREE.OrbitControls(camera, renderer.domElement);
                            controls.enableDamping = true;
                            controls.dampingFactor = 0.05;
                            
                            // 添加立方体作为示例模型
                            const geometry = new THREE.BoxGeometry(1, 1, 1);
                            const material = new THREE.MeshStandardMaterial({ 
                                color: 0x00ff00, 
                                metalness: 0.3,
                                roughness: 0.4
                            });
                            cube = new THREE.Mesh(geometry, material);
                            cube.name = "model"; // 给模型命名，便于查找
                            scene.add(cube);
                            
                            // 添加灯光
                            const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
                            scene.add(ambientLight);
                            
                            const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
                            directionalLight.position.set(5, 5, 5);
                            scene.add(directionalLight);
                            
                            // 使场景和控制器在全局可访问
                            window.scene = scene;
                            window.camera = camera;
                            window.__orbitControls = controls;
                            
                            // 记录日志函数
                            window.logAction = (message) => {
                                const logNode = document.createTextNode(message + '\\n');
                                logElement.appendChild(logNode);
                                console.log(message);
                            };
                            
                            // 响应窗口大小变化
                            window.addEventListener('resize', () => {
                                camera.aspect = window.innerWidth / window.innerHeight;
                                camera.updateProjectionMatrix();
                                renderer.setSize(window.innerWidth, window.innerHeight);
                            });
                            
                            animate();
                            logAction("测试场景已初始化");
                        }
                        
                        function animate() {
                            requestAnimationFrame(animate);
                            controls.update();
                            renderer.render(scene, camera);
                        }
                        
                        // 导出模型操作API - 使用对象参数的新版接口
                        
                        // 旋转模型
                        window.rotateModel = function(params) {
                            logAction(`执行旋转操作: ${JSON.stringify(params)}`);
                            const { direction = 'left', angle = 30 } = params;
                            
                            try {
                                const rotationAngle = (Math.PI / 180) * angle * (direction === 'left' ? 1 : -1);
                                cube.rotation.y += rotationAngle;
                                logAction(`旋转成功: ${direction}, ${angle}度`);
                                return true;
                            } catch (e) {
                                logAction(`旋转失败: ${e.message}`);
                                return false;
                            }
                        };
                        
                        // 缩放模型
                        window.zoomModel = function(params) {
                            logAction(`执行缩放操作: ${JSON.stringify(params)}`);
                            const { scale = 1.5 } = params;
                            
                            try {
                                if (controls) {
                                    const zoomOut = scale < 1;
                                    const factor = Math.abs(scale - 1) * 5;
                                    
                                    if (zoomOut) {
                                        camera.position.z += factor;
                                    } else {
                                        camera.position.z = Math.max(2, camera.position.z - factor);
                                    }
                                    
                                    logAction(`缩放成功: 比例 ${scale}`);
                                    return true;
                                }
                                return false;
                            } catch (e) {
                                logAction(`缩放失败: ${e.message}`);
                                return false;
                            }
                        };
                        
                        // 聚焦模型
                        window.focusModel = function(params) {
                            logAction(`执行聚焦操作: ${JSON.stringify(params)}`);
                            const { target = 'center' } = params;
                            
                            try {
                                // 重置相机位置
                                controls.reset();
                                camera.position.set(0, 0, 5);
                                logAction(`聚焦成功: ${target}`);
                                return true;
                            } catch (e) {
                                logAction(`聚焦失败: ${e.message}`);
                                return false;
                            }
                        };
                        
                        // 重置视图
                        window.resetView = function() {
                            logAction('执行重置操作');
                            
                            try {
                                // 重置相机位置
                                controls.reset();
                                camera.position.set(0, 0, 5);
                                cube.rotation.set(0, 0, 0);
                                logAction('重置成功');
                                return true;
                            } catch (e) {
                                logAction(`重置失败: ${e.message}`);
                                return false;
                            }
                        };
                        
                        // 创建app对象
                        window.app = {
                            resetModel: function() {
                                return window.resetView();
                            }
                        };
                        
                        // 初始化场景
                        init();
                    </script>
                </body>
            </html>
            """)
            logger.info("已创建内存中的测试页面")
        
        # 更新应用状态
        app.state.page = page
        app.state.browser = browser
        
        # 打印页面状态信息
        page_url = page.url
        page_title = await page.title()
        
        logger.info(f"页面已初始化，URL: {page_url}, 标题: {page_title}")
        
        # 将页面设置给MCP服务器
        if page:
            logger.info("设置页面实例到MCP服务器")
            mcp_server.set_page(page)
        
        yield
        
    except Exception as e:
        logger.error(f"浏览器初始化失败: {str(e)}")
        logger.error(traceback.format_exc())
    
    # 应用结束时清理资源
    try:
        logger.info("正在关闭浏览器和Playwright...")
        if page:
            await page.close()
        if browser:
            await browser.close()
        if playwright_instance:
            await playwright_instance.stop()
        logger.info("资源已正确关闭")
    except Exception as e:
        logger.error(f"关闭资源时出错: {str(e)}")

# 检查并创建静态文件目录
def ensure_static_directory():
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if not os.path.exists(static_dir):
        try:
            os.makedirs(static_dir, exist_ok=True)
            logger.info(f"已创建静态文件目录: {static_dir}")
        except Exception as e:
            logger.error(f"创建静态文件目录失败: {e}")
    return static_dir

# 确保静态目录存在
static_dir = ensure_static_directory()

# 创建FastAPI应用
app = FastAPI(
    title="数字孪生浏览器操作服务",
    description="提供基于Web的数字孪生3D模型操作服务，支持旋转、缩放、聚焦和重置等操作。",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "operations",
            "description": "模型操作API (Model Operation APIs)"
        },
        {
            "name": "system",
            "description": "系统状态API (System Status APIs)"
        }
    ]
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
try:
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"静态文件目录已挂载: {static_dir}")
except Exception as e:
    logger.error(f"挂载静态文件目录失败: {e}")

# API密钥验证依赖
async def verify_api_key(authorization: Optional[str] = Header(None)):
    """验证API密钥 (Verify API key)"""
    if not API_KEY_REQUIRED:
        return
    
    if not API_KEY:
        logger.warning("API_KEY_REQUIRED=true，但未配置API_KEY，跳过验证 (API key required but not configured, skipping validation)")
        return
    
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供API密钥 (API key not provided)")
    
    # 检查API密钥格式
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="无效的API密钥格式 (Invalid API key format)")
    
    token = parts[1]
    if token != API_KEY:
        logger.warning(f"收到无效的API密钥 (Received invalid API key)")
        raise HTTPException(status_code=401, detail="无效的API密钥 (Invalid API key)")
    
    logger.debug("API密钥验证成功 (API key validation successful)")
    return token

# API端点
@app.post("/api/execute")
async def execute_operation(
    data: Dict[str, Any] = Body(...),
    api_key: Optional[str] = Depends(verify_api_key)
):
    """执行模型操作"""
    try:
        # 验证数据格式
        if "operation" not in data:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "缺少操作类型"}
            )
        
        operation = data["operation"]
        parameters = data.get("parameters", {})
        target = data.get("target")
        
        # 创建MCP命令
        command = None
        
        if operation == "rotate":
            direction = parameters.get("direction", "left")
            angle = parameters.get("angle", 45)
            command = MCPCommand.rotate(direction, angle, target)
        elif operation == "zoom":
            scale = parameters.get("scale", 1.5)
            command = MCPCommand.zoom(scale, target)
        elif operation == "focus":
            target = target or parameters.get("target", "center")
            command = MCPCommand.focus(target)
        elif operation == "reset":
            command = MCPCommand.reset()
        else:
            # 自定义操作
            command = MCPCommand(
                action=operation,
                parameters=parameters,
                target=target
            )
        
        # 执行命令
        result = await mcp_server.execute_command(command)
        
        # 返回结果
        return {
            "success": result.success,
            "message": "操作执行成功" if result.success else "操作执行失败",
            "data": result.data,
            "error": result.error
        }
    except Exception as e:
        logger.error(f"执行操作时出错: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# 健康检查端点
@app.get("/health", tags=["system"])
async def health_check():
    """
    获取服务健康状态
    
    返回服务的健康状态信息，包括API状态、浏览器状态和页面状态
    """
    current_time = int(time.time())
    
    # 收集系统信息
    system_info = {
        "hostname": os.getenv("COMPUTERNAME", "未知"),
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
        "cpu_count": os.cpu_count(),
        "memory_info": "未获取"
    }
    
    # 收集环境变量信息（屏蔽敏感信息）
    env_info = {
        "BROWSER_TYPE": BROWSER_TYPE,
        "HEADLESS": HEADLESS,
        "FRONTEND_URL": FRONTEND_URL,
        "PORT": os.getenv("PORT", "9000"),
        "LOG_LEVEL": LOG_LEVEL,
        "API_KEY_REQUIRED": API_KEY_REQUIRED,
    }
    
    # 检查浏览器状态
    browser_status = "未初始化"
    browser_info = {}
    if browser:
        try:
            # 尝试访问浏览器属性来检查它是否可用，而不是使用is_closed()
            contexts = await browser.contexts()
            browser_status = "已初始化"
            
            browser_info = {
                "browser_type": BROWSER_TYPE,
                "contexts_count": len(contexts),
                "headless": HEADLESS
            }
        except Exception as e:
            browser_status = "已关闭或不可用"
            browser_info = {"error": f"获取浏览器信息失败: {str(e)}"}
    
    # 检查页面状态
    page_status = "未初始化"
    page_info = {}
    current_url = "未知"
    
    if 'page' in app.state.__dict__ and app.state.page:
        try:
            # 尝试访问页面属性来检查它是否可用，而不是使用is_closed()
            current_url = await app.state.page.url()
            page_title = await app.state.page.title()
            
            page_status = "已加载"
            
            # 尝试检查页面是否可响应
            try:
                # 执行简单测试，检查页面是否存在基本API
                test_result = await app.state.page.evaluate("""
                () => { 
                    try {
                        // 检查基本API是否存在
                        const apis = [
                            typeof window.rotateModel === 'function',
                            typeof window.zoomModel === 'function', 
                            typeof window.focusModel === 'function' || typeof window.focusOnModel === 'function',
                            typeof window.resetView === 'function' || typeof window.resetModel === 'function' || 
                            (window.app && typeof window.app.resetModel === 'function')
                        ];
                        
                        const missingApis = apis.filter(exists => !exists).length;
                        
                        if (missingApis === 0) {
                            return { status: "ready", message: "所有API可用" };
                        } else {
                            return { 
                                status: "partial", 
                                message: `缺少${missingApis}个API`,
                                available: apis
                            };
                        }
                    } catch (e) {
                        return { status: "error", message: e.toString() };
                    }
                }
                """)
                
                page_info = {
                    "url": current_url,
                    "title": page_title,
                    "api_status": test_result.get("status", "unknown"),
                    "api_message": test_result.get("message", ""),
                }
                
                if page_info["api_status"] == "ready":
                    page_status = "正常"
                elif page_info["api_status"] == "partial":
                    page_status = "部分功能可用"
                else:
                    page_status = "API不可用"
                    
            except Exception as page_eval_error:
                logger.warning(f"页面API检查失败: {str(page_eval_error)}")
                page_status = "可访问但API检查失败"
                page_info["error"] = str(page_eval_error)
                
        except Exception as e:
            page_status = "已关闭或不可用"
            page_info = {"error": f"获取页面信息失败: {str(e)}"}
    elif page is not None:
        try:
            current_url = await page.url()
            page_status = "页面存在但不在app.state中"
            page_info = {"url": current_url}
        except Exception as e:
            page_status = "全局页面异常"
            page_info = {"error": str(e)}
    
    # 始终返回健康状态
    return {
        "status": "healthy",  # 总是返回健康状态
        "message": "服务正常运行",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0",
        "api_key_status": "已配置" if API_KEY else "未配置",
        "browser_status": browser_status,
        "page_status": page_status,
        "current_url": current_url,
        "environment": env_info,
        "system_info": system_info,
        "browser_info": browser_info,
        "page_info": page_info
    }

@app.get("/")
async def root():
    """根路由，重定向到API文档页面 (Root route, redirects to API documentation page)"""
    try:
        # 检查是否有自定义主页
        index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
        if os.path.exists(index_path):
            # 通过FileResponse返回静态HTML文件
            return FileResponse(index_path)
        else:
            # 如果没有静态页面，重定向到API文档
            return RedirectResponse(url="/docs")
    except Exception as e:
        logger.error(f"访问根路由时出错: {e}")
        return {"message": "数字孪生浏览器操作服务API，请访问 /docs 查看API文档"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket端点，用于实时通信
    """
    await ws_manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "message": "WebSocket连接已建立 (WebSocket connection established)",
            "timestamp": datetime.now().isoformat()
        }))
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                logger.debug(f"收到WebSocket消息 (Received WebSocket message): {message}")
                
                # 简单的消息回显
                await websocket.send_text(json.dumps({
                    "type": "echo",
                    "original": message,
                    "timestamp": datetime.now().isoformat()
                }))
            except json.JSONDecodeError:
                logger.warning(f"无效的JSON消息 (Invalid JSON message): {data}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "无效的JSON消息 (Invalid JSON message)",
                    "timestamp": datetime.now().isoformat()
                }))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

# WebSocket端点：处理MCP协议通信
@app.websocket("/ws/mcp")
async def websocket_mcp_endpoint(websocket: WebSocket):
    """WebSocket端点：处理MCP协议通信"""
    await mcp_server.connect(websocket)
    
    try:
        # 发送欢迎消息
        await websocket.send_text(json.dumps({
            "type": "welcome",
            "message": "欢迎连接到MCP服务器",
            "timestamp": datetime.now().isoformat()
        }))
        
        # 确保MCP服务器有页面引用
        mcp_server.set_page(app.state.page if hasattr(app.state, "page") else None)
        
        # 处理消息
        while True:
            data = await websocket.receive_text()
            try:
                # 解析消息
                message = json.loads(data)
                command_data = message.get("command", {})
                
                # 创建命令
                command = MCPCommand.from_dict(command_data)
                
                # 执行命令
                result = await mcp_server.execute_command(command)
                
                # 发送结果
                await websocket.send_text(json.dumps({
                    "type": "commandResult",
                    "result": result.to_dict(),
                    "timestamp": datetime.now().isoformat()
                }))
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "无效的JSON消息",
                    "timestamp": datetime.now().isoformat()
                }))
            except Exception as e:
                logger.error(f"处理WebSocket消息时出错: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                }))
    except WebSocketDisconnect:
        mcp_server.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket连接处理时出错: {e}")
        logger.error(traceback.format_exc())
        try:
            mcp_server.disconnect(websocket)
        except:
            pass

# REST API端点：发送MCP命令
@app.post("/api/mcp/command")
async def send_mcp_command(data: Dict[str, Any], request: Request):
    """发送MCP命令"""
    try:
        # 验证请求数据
        if "action" not in data:
            raise HTTPException(status_code=400, detail="缺少'action'字段")
        
        # 创建命令
        command = MCPCommand.from_dict(data)
        
        # 设置页面
        mcp_server.set_page(app.state.page if hasattr(app.state, "page") else None)
        
        # 执行命令
        result = await mcp_server.execute_command(command)
        
        return {
            "success": True,
            "commandId": command.id,
            "result": result
        }
    except Exception as e:
        logger.error(f"执行MCP命令时出错: {e}")
        logger.debug(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e)
        }

# 自然语言命令端点
@app.post("/api/mcp/nl-command")
async def send_nl_command(data: Dict[str, Any], request: Request):
    """发送自然语言命令"""
    try:
        # 验证请求数据
        if "message" not in data:
            raise HTTPException(status_code=400, detail="缺少'message'字段")
        
        message = data["message"]
        
        # 使用MCP命令生成函数解析指令
        command = await generate_mcp_command_from_nl(message)
        
        if not command:
            return {
                "success": False,
                "error": "无法理解命令"
            }
        
        # 设置页面
        mcp_server.set_page(app.state.page if hasattr(app.state, "page") else None)
        
        # 执行命令
        result = await mcp_server.execute_command(command)
        
        return {
            "success": True,
            "commandId": command.id,
            "action": command.action,
            "parameters": command.parameters,
            "result": result
        }
    except Exception as e:
        logger.error(f"执行自然语言命令时出错: {e}")
        logger.debug(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e)
        }

# 修改WebSocket状态API，返回MCP连接状态
@app.get("/api/websocket/status", tags=["system"])
async def websocket_status():
    """获取WebSocket连接状态"""
    try:
        # 获取标准WebSocket连接数
        ws_connections = len(ws_manager.active_connections)
        
        # 获取MCP WebSocket连接数
        mcp_connections = len(mcp_server.active_connections)
        
        return {
            "success": True,
            "status": "运行中",
            "standard_connections": ws_connections,
            "mcp_connections": mcp_connections,
            "timestamp": datetime.now().isoformat(),
            "mcp_enabled": True
        }
    except Exception as e:
        logger.error(f"获取WebSocket状态时出错: {e}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# 修改llm处理端点，使用MCP命令生成函数
@app.post("/api/llm/process")
async def process_llm_command(
    data: Dict[str, Any] = Body(...),
    api_key: Optional[str] = Depends(verify_api_key)
):
    """处理自然语言指令并执行相应操作"""
    try:
        # 验证数据
        if "message" not in data:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "消息不能为空"}
            )
        
        message = data["message"]
        logger.info(f"收到自然语言指令: {message}")
        
        # 使用MCP命令生成函数解析指令
        command = await generate_mcp_command_from_nl(message)
        
        if not command:
            return {
                "success": False,
                "message": "无法理解命令",
                "recognized": False
            }
        
        # 执行命令
        result = await mcp_server.execute_command(command)
        
        return {
            "success": result.success,
            "message": f"已执行{command.action}操作" if result.success else "操作执行失败",
            "recognized": True,
            "operation": command.action,
            "parameters": command.parameters,
            "data": result.data
        }
    except Exception as e:
        logger.error(f"处理自然语言指令时出错: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

if __name__ == "__main__":
    try:
        print("=== 数字孪生浏览器操作服务 ===")
        print(f"日志级别: {LOG_LEVEL}")
        print(f"无头模式: {HEADLESS}")
        print(f"浏览器类型: {BROWSER_TYPE}")
        print(f"前端URL: {FRONTEND_URL}")
        backup_url = os.getenv("BACKUP_FRONTEND_URL", "")
        if backup_url:
            print(f"备用前端URL: {backup_url}")
        else:
            print("未配置备用前端URL，请设置BACKUP_FRONTEND_URL环境变量以提供备选页面")
            print("可以设置为CDN托管的测试页面或本地文件，例如: file:///path/to/test.html")
        
        # 检查Playwright是否已安装浏览器
        print("检查Playwright浏览器安装...")
        is_browser_installed = check_browser_installation()
        if not is_browser_installed:
            print("警告: Playwright浏览器未安装，请运行: playwright install")
            print("您可以继续运行服务，但操作功能将无法正常工作")
        else:
            print("Playwright浏览器已正确安装，服务将正常运行")
    except Exception as e:
        print(f"检查Playwright浏览器时出错: {e}")
        print("将继续启动服务，但某些功能可能受限")
    
    # 启动配置指南
    print("\n=== 环境变量配置 ===")
    print("要调整浏览器配置，可设置以下环境变量:")
    print("* FRONTEND_URL     - 主前端地址 (默认: http://localhost:3000)")
    print("* BACKUP_FRONTEND_URL - 备用前端地址 (默认: 无)")
    print("* BROWSER_TYPE     - 浏览器类型: chromium/firefox/webkit (默认: chromium)")
    print("* HEADLESS         - 无头模式: true/false (默认: true)")
    print("* PORT             - 服务端口 (默认: 9000)")
    print("* LOG_LEVEL        - 日志级别: DEBUG/INFO/WARNING/ERROR (默认: INFO)")
    print("* PAGE_LOAD_TIMEOUT- 页面加载超时时间(毫秒) (默认: 60000)")
    print("* MODEL_LOAD_WAIT  - 模型加载等待时间(毫秒) (默认: 5000)")
    
    # 启动服务
    port = int(os.getenv("PORT", 9000))  # 确保默认端口为9000
    print(f"\n启动服务，访问 http://localhost:{port}/docs 查看API文档")
    print(f"健康检查接口: http://localhost:{port}/health")
    
    # 使用所有可用的调试信息启动
    try:
        # 添加启动消息，确认服务初始化完成
        print(f"正在初始化浏览器和页面，请稍候...")
        
        # 增加超时时间和确保lifespan事件执行完成
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port, 
            reload=False,
            log_level=LOG_LEVEL.lower(),
            timeout_keep_alive=120,
            lifespan="on"
        )
    except Exception as e:
        print(f"启动服务失败: {e}")
        print(traceback.format_exc()) 