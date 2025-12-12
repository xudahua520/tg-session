import asyncio
import base64
import io
import json
import logging
import os
import sys
import time
import qrcode
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TG-Web")

# --- 路径配置 ---
# 强制指定容器内的保存路径，确保数据保存在容器里
SESSIONS_DIR = "/app/sessions"
# 确保目录存在
os.makedirs(SESSIONS_DIR, exist_ok=True)

app = FastAPI()

# --------------------------
# 页面配置变量
# --------------------------
APP_VERSION = "v1.0.0 Pro"
PERSONAL_SITE_URL = "https://github.com/xudahua520"
AVATAR_URL = "https://q1.qlogo.cn/g?b=qq&nk=95317341&s=640" 

# --------------------------
# 前端 HTML
# --------------------------
html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TG Session丨管理面板</title>
    <link rel="icon" href="https://telegram.org/img/favicon.ico" type="image/x-icon">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        :root {{ 
            --primary-color: #0088cc; /* TG Blue */
            --bg-color: #f0f2f5; 
            --card-radius: 16px;
        }}
        body {{ 
            background-color: var(--bg-color); 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
            color: #333;
        }}
        .content-wrapper {{ flex: 1; }}
        
        /* --- 头部样式 --- */
        .header {{ 
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.04); 
            margin-bottom: 25px; 
            padding: 0; 
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        .header-inner {{
            height: 70px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        
        .logo-group {{ display: flex; align-items: center; }}
        .logo-icon {{ 
            width: 42px; 
            height: 42px; 
            background: var(--primary-color); 
            border-radius: 50%; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            color: white; 
            margin-right: 15px; 
            font-size: 24px; 
            box-shadow: 0 4px 10px rgba(0, 136, 204, 0.3);
        }}
        
        .badge-link {{
            text-decoration: none;
            padding: 6px 12px;
            border-radius: 20px;
            font-weight: 500;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            letter-spacing: 0.3px;
        }}
        .badge-link:hover {{ transform: translateY(-2px); opacity: 0.9; box-shadow: 0 2px 5px rgba(0,0,0,0.1); color: #fff !important; }}
        
        /* --- 通知栏 --- */
        .notice-bar {{
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 2px 15px rgba(0,0,0,0.03);
            padding: 0 20px;
            display: flex;
            align-items: center;
            height: 54px;
            margin-bottom: 25px;
            overflow: hidden;
        }}
        .notice-icon {{ margin-right: 15px; font-size: 1.2rem; animation: pulse 2s infinite; }}
        .notice-content {{ flex: 1; overflow: hidden; white-space: nowrap; }}
        .marquee {{
            display: inline-block;
            padding-left: 100%;
            animation: marquee 25s linear infinite;
            color: #555;
            font-weight: 500;
        }}
        @keyframes marquee {{ 0% {{ transform: translate(0, 0); }} 100% {{ transform: translate(-100%, 0); }} }}
        @keyframes pulse {{ 0% {{ transform: scale(1); }} 50% {{ transform: scale(1.15); }} 100% {{ transform: scale(1); }} }}
        
        /* --- 卡片通用 --- */
        .card {{ 
            border: none; 
            border-radius: var(--card-radius); 
            box-shadow: 0 5px 20px rgba(0,0,0,0.04); 
            margin-bottom: 20px; 
            background: #fff;
            transition: transform 0.2s;
        }}
        .card:hover {{ transform: translateY(-2px); }}
        .card-header {{ 
            background: transparent; 
            border-bottom: 1px solid #f2f2f2; 
            font-weight: 700; 
            padding: 20px 25px; 
            color: #444;
            display: flex; 
            align-items: center;
        }}
        .card-header i {{ margin-right: 10px; color: var(--primary-color); font-size: 1.1em; }}
        .card-body {{ padding: 25px; }}

        /* --- 输入框标签调整 --- */
        .input-group-text {{
            min-width: 120px; 
            justify-content: flex-start;
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-right: none;
            color: #666;
            font-weight: 500;
            font-size: 0.9rem;
        }}
        .input-group-text i {{ width: 20px; text-align: center; margin-right: 8px; color: var(--primary-color); }}
        .form-control {{ border: 1px solid #e9ecef; }}
        .form-control:focus {{ box-shadow: none; border-color: var(--primary-color); }}
        
        /* 代理类型选择框 */
        .form-select-proxy {{
            max-width: 110px;
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-right: 1px solid #ddd;
            font-weight: 600;
            color: #555;
        }}
        .form-select-proxy:focus {{ border-color: var(--primary-color); box-shadow: none; }}

        /* --- 按钮样式 --- */
        .btn-custom {{
            border-radius: 10px;
            padding: 10px 20px;
            font-weight: 600;
            transition: all 0.3s;
            width: 100%;
            margin-bottom: 10px;
            border: none;
        }}
        .btn-primary-custom {{ background: var(--primary-color); color: white; box-shadow: 0 4px 12px rgba(0, 136, 204, 0.2); }}
        .btn-primary-custom:hover {{ background: #0077b3; transform: translateY(-1px); color: white; }}
        
        .btn-secondary-custom {{ background: #fff; border: 2px solid #e0e0e0; color: #555; }}
        .btn-secondary-custom:hover {{ border-color: #bbb; background: #f8f9fa; color: #333; }}
        
        .btn-restart {{
            background: #fff0f0;
            color: #dc3545;
            border: 1px dashed #dc3545;
            margin-top: 15px;
        }}
        .btn-restart:hover {{ background: #dc3545; color: white; }}

        /* --- 日志窗口 (浅色风格) --- */
        .log-window {{ 
            background: #fcfcfc;  
            color: #333;          
            padding: 20px; 
            border-radius: 12px; 
            height: 420px; 
            overflow-y: auto; 
            font-family: 'JetBrains Mono', 'Consolas', monospace; 
            font-size: 13px; 
            line-height: 1.6; 
            border: 1px solid #f0f0f0; 
        }}
        .log-entry {{ margin-bottom: 6px; padding-left: 10px; border-left: 3px solid #ddd; }}
        .log-info {{ border-color: #0088cc; color: #005f8f; }}
        .log-success {{ border-color: #28a745; color: #1e7e34; }}
        .log-error {{ border-color: #dc3545; color: #b02a37; }}
        .log-warning {{ border-color: #ffc107; color: #d39e00; }}
        
        /* --- 结果展示区 --- */
        .session-box {{ 
            background: #fff; 
            color: #333; 
            padding: 20px; 
            border-radius: 12px; 
            display: none; 
            margin-top: 20px; 
            border: 1px solid #e0e0e0;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            position: relative;
        }}
        .session-title {{
            font-size: 0.9rem;
            color: #666;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #f0f0f0;
            padding-bottom: 10px;
            font-weight: 600;
        }}
        .session-content {{
            font-family: 'Consolas', 'Monaco', monospace;
            word-break: break-all;
            color: #d63384; 
            background-color: #fcfcfc;
            border: 1px solid #f1f1f1;
            padding: 12px;
            border-radius: 8px;
            font-size: 0.9rem;
            max-height: 120px;
            overflow-y: auto;
        }}
        .file-path-tag {{
            background: #f8f9fa;
            padding: 10px 15px;
            border-radius: 8px;
            margin-top: 15px;
            font-size: 0.85rem;
            color: #555;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid #eee;
        }}

        /* --- 页脚样式 (缩小左右图标) --- */
        .site-footer {{ 
            background-color: #fff; 
            padding: 40px 0 25px; 
            text-align: center; 
            border-top: 1px solid #eee; 
            margin-top: auto; 
        }}
        .social-container {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 25px;
            margin-bottom: 30px;
        }}
        .social-link {{
            width: 36px;  
            height: 36px; 
            background-color: #343a40;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            text-decoration: none;
        }}
        .social-link svg {{ width: 16px; height: 16px; fill: #fff; }} 
        .social-link:hover {{ transform: translateY(-3px); background-color: #000; }}
        
        .center-avatar {{
            width: 65px;
            height: 65px;
            border-radius: 50%;
            border: 4px solid #fff;
            box-shadow: 0 5px 15px rgba(0,0,0,0.15);
            overflow: hidden;
            margin: 0 10px;
            transition: transform 0.3s;
        }}
        .center-avatar img {{ width: 100%; height: 100%; object-fit: cover; }}
        .center-avatar:hover {{ transform: scale(1.05); }}

        .footer-copyright {{ color: #6c757d; font-size: 0.85rem; }}
        .footer-copyright a {{ color: #6c757d; text-decoration: none; }}
        .footer-copyright a:hover {{ color: var(--primary-color); }}
        
        /* 加载遮罩 */
        #loadingOverlay {{
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(5px);
            z-index: 9999;
            display: flex; flex-direction: column; justify-content: center; align-items: center;
            display: none;
        }}
        
        /* 二维码区域 */
        .qr-container {{ 
            text-align: center; 
            margin: 30px 0; 
            display: none; 
            background: #fff;
            padding: 20px;
            border-radius: 12px;
            position: relative;
        }}
        .qr-container img {{ border: 8px solid #fff; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
        
        /* 二维码过期遮罩 */
        .qr-overlay {{
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(4px);
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 10;
            display: none;
        }}
        .qr-timer-text {{
            font-size: 0.9rem;
            color: #666;
            margin-top: 15px;
            font-weight: 500;
        }}
        .timer-count {{ color: #dc3545; font-weight: bold; margin: 0 4px; }}
    </style>
</head>
<body>

<div id="loadingOverlay">
    <div class="spinner-border text-primary" style="width: 3rem; height: 3rem;" role="status"></div>
    <h5 class="mt-4 fw-light text-secondary">系统重启中，请稍候...</h5>
</div>

<div class="content-wrapper">
    <!-- 头部 -->
    <div class="header">
        <div class="container">
            <div class="header-inner">
                <div class="logo-group">
                    <div class="logo-icon"><i class="fab fa-telegram-plane"></i></div>
                    <div>
                        <h5 class="m-0 fw-bold" style="color: #333;">TG Session</h5>
                    </div>
                </div>
                
                <div class="d-flex gap-2 align-items-center">
                    <a href="https://github.com/xudahua520/tg-session" target="_blank" class="badge bg-dark badge-link text-white">
                        <i class="fab fa-github me-1"></i> GitHub
                    </a>
                    <a href="https://hub.docker.com/r/xudahua520/tg-session" target="_blank" class="badge bg-primary badge-link text-white">
                        <i class="fab fa-docker me-1"></i> Docker
                    </a>
                    <a href="https://github.com/xudahua520?tab=repositories" target="_blank" class="badge bg-info text-dark badge-link">
                        <i class="fas fa-cubes me-1"></i> 更多
                    </a>
                </div>
            </div>
        </div>
    </div>

    <!-- 滚动通知 -->
    <div class="container px-4">
        <div class="notice-bar">
            <div class="notice-icon text-primary">📢</div>
            <div class="notice-content">
                <div class="marquee">
                    欢迎使用 TG Session！本系统支持二维码及手机号登录，数据仅保存在您本地，Session 是您的账号凭证，请务必妥善保管。
                </div>
            </div>
            <div class="notice-arrow"><i class="fas fa-chevron-right text-muted"></i></div>
        </div>
    </div>

    <!-- 主体 -->
    <div class="container px-4">
        <div class="row g-4">
            <!-- 左侧配置 -->
            <div class="col-lg-5">
                <div class="card h-100">
                    <div class="card-header"><i class="fas fa-cog"></i> 参数配置中心</div>
                    <div class="card-body">
                        <form id="configForm">
                            <label class="form-label text-muted small fw-bold">API 配置 (my.telegram.org)</label>
                            
                            <div class="input-group mb-3">
                                <span class="input-group-text"><i class="fas fa-id-card"></i> API ID</span>
                                <input type="number" class="form-control" id="apiId" value="6627460" placeholder="请输入数字 ID">
                            </div>
                            <div class="input-group mb-4">
                                <span class="input-group-text"><i class="fas fa-key"></i> API Hash</span>
                                <input type="text" class="form-control" id="apiHash" value="27a53a0965e486a2bc1b1fcde473b1c4" placeholder="请输入 Hash">
                            </div>

                            <label class="form-label text-muted small fw-bold d-flex justify-content-between">
                                网络代理
                                <div class="form-check form-switch">
                                    <input class="form-check-input" type="checkbox" id="enableProxy">
                                </div>
                            </label>
                            
                            <div class="input-group mb-4">
                                <select class="form-select form-select-proxy" id="proxyType">
                                    <option value="socks5" selected>SOCKS5</option>
                                    <option value="http">HTTP</option>
                                    <option value="socks4">SOCKS4</option>
                                </select>
                                <input type="text" class="form-control" id="proxyFull" value="192.168.2.6:7891" placeholder="IP:端口 (例如 127.0.0.1:7890)">
                            </div>

                            <div class="mt-5">
                                <!-- 登录操作组 -->
                                <div id="loginGroup">
                                    <button type="button" class="btn-custom btn-primary-custom" onclick="startLogin('qr')">
                                        <i class="fas fa-qrcode me-2"></i>二维码登录 (推荐)
                                    </button>
                                    <button type="button" class="btn-custom btn-secondary-custom" onclick="startLogin('phone')">
                                        <i class="fas fa-mobile-alt me-2"></i>手机号登录
                                    </button>
                                </div>
                                
                                <!-- 停止按钮 -->
                                <div id="stopGroup" class="d-none">
                                    <button type="button" class="btn-custom btn-danger" onclick="stopProcess()">
                                        <i class="fas fa-stop-circle me-2"></i>停止当前任务
                                    </button>
                                </div>

                                <!-- 重启按钮 -->
                                <button type="button" onclick="restartService()" class="btn-custom btn-restart">
                                    <i class="fas fa-sync-alt me-2"></i>重启后台服务
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

            <!-- 右侧终端 -->
            <div class="col-lg-7">
                <div class="card h-100">
                    <div class="card-header d-flex justify-content-between">
                        <span><i class="fas fa-terminal"></i> 运行终端</span>
                        <button class="btn btn-sm btn-link text-decoration-none text-muted" onclick="clearLog()">
                            <i class="fas fa-trash-alt me-1"></i>清空
                        </button>
                    </div>
                    <div class="card-body bg-light position-relative">
                        <!-- 二维码层 -->
                        <div id="qrContainer" class="qr-container">
                            <h6 class="mb-3 text-dark fw-bold">请使用 Telegram 扫码</h6>
                            <div style="position: relative; display: inline-block;">
                                <img id="qrImage" src="" alt="QR Code" width="240" height="240">
                                <!-- 遮罩层 -->
                                <div id="qrOverlay" class="qr-overlay">
                                    <i class="fas fa-exclamation-circle text-danger mb-3" style="font-size: 2rem;"></i>
                                    <h6 class="text-secondary mb-3">二维码已过期</h6>
                                    <button class="btn btn-sm btn-primary" onclick="refreshQr()">
                                        <i class="fas fa-sync-alt me-1"></i> 刷新二维码
                                    </button>
                                </div>
                            </div>
                            <div id="qrTimer" class="qr-timer-text">有效期剩余 <span class="timer-count" id="timerCount">60</span> 秒</div>
                        </div>

                        <!-- 交互输入层 -->
                        <div id="inputArea" class="input-group mb-3 d-none shadow-sm" style="position:absolute; bottom:20px; left:20px; right:20px; width:auto; z-index:10;">
                            <input type="text" class="form-control border-primary" id="userInput" placeholder="在此输入验证码或密码...">
                            <button class="btn btn-primary" onclick="sendInput()">发送 <i class="fas fa-paper-plane ms-1"></i></button>
                        </div>

                        <!-- 日志层 -->
                        <div id="logWindow" class="log-window">
                            <div class="log-entry log-info">> 系统就绪，等待指令...</div>
                        </div>

                        <!-- 结果层 -->
                        <div id="resultBox" class="session-box">
                            <div class="session-title">
                                <span><i class="fas fa-key me-2 text-primary"></i>Session String</span>
                                <button class="btn btn-sm btn-outline-secondary py-0" style="font-size:0.8rem;" onclick="copySession()">
                                    <i class="far fa-copy me-1"></i>复制
                                </button>
                            </div>
                            <div id="sessionText" class="session-content"></div>
                            
                            <div class="file-path-tag">
                                <div><i class="fas fa-file-alt me-2"></i><span id="serverPath">...</span></div>
                                <a id="downloadBtn" href="#" target="_blank" class="text-decoration-none text-success fw-bold">
                                    <i class="fas fa-download me-1"></i>下载
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- 页脚 -->
<footer class="site-footer">
    <div class="container">
        <!-- 图标容器 -->
        <div class="social-container">
            <a href="https://github.com/xudahua520/tg-session" target="_blank" class="social-link" title="Github">
                <svg viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
            </a>
            <a href="mailto:xudahua520@gmail.com" class="social-link" title="Email">
                <svg viewBox="0 0 24 24"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>
            </a>
            <a href="{PERSONAL_SITE_URL}" target="_blank" class="center-avatar">
                <img src="{AVATAR_URL}" alt="Admin">
            </a>
            <a href="https://t.me/Deva520" target="_blank" class="social-link" title="Telegram">
                <svg viewBox="0 0 24 24"><path d="M20.665 3.717l-17.73 6.837c-1.21.486-1.203 1.161-.222 1.462l4.552 1.42 10.532-6.645c.498-.303.953-.14.579.192l-8.533 7.701h-.002l.002.001-.314 4.692c.46 0 .663-.211.921-.46l2.211-2.15 4.599 3.397c.848.467 1.457.227 1.668-.785l3.019-14.228c.309-1.239-.473-1.8-1.282-1.434z"/></svg>
            </a>
            <a href="tencent://message/?uin=95317341" class="social-link" title="QQ"><svg viewBox="0 0 24 24"><path d="M12 0C5.373 0 0 5.373 0 12c0 6.627 5.373 12 12 12s12-5.373 12-12C24 5.373 18.627 0 12 0zm0 3c1.77 0 3.32.72 4.47 1.88C17.62 6.03 18 7.37 18 9c0 1.63-.38 2.97-1.53 4.12C15.32 14.28 13.77 15 12 15s-3.32-.72-4.47-1.88C6.38 11.97 6 10.63 6 9c0-1.63.38-2.97 1.53-4.12C8.68 3.72 10.23 3 12 3zm0 13c-2.67 0-5.18-.87-7.23-2.34C3.65 15.6 3 18.23 3 19c0 .55.45 1 1 1h16c.55 0 1-.45 1-1 0-.77-.65-3.4-1.77-5.34C17.18 15.13 14.67 16 12 16z"/></svg></a>
        </div>        
        <div class="footer-copyright">
            <p class="mb-1">
                © 2024 - 2025 By Deva 用于互联网爱好者学习和研究 <span class="separator">|</span> <span class="badge bg-secondary">{APP_VERSION}</span>
            </p>
            <p class="mb-0">
                项目: <a href="https://github.com/xudahua520/tg-session" target="_blank" class="fw-bold text-primary">TG Session</a>
            </p>
        </div>
    </div>
</footer>

<script>
    let ws = null;
    let isProcessing = false;
    let timerInterval = null;

    // --- 重启逻辑 ---
    function restartService() {{
        if(!confirm("确定要重启后台服务吗？\\n这将中断当前所有的操作任务。")) return;
        
        document.getElementById('loadingOverlay').style.display = 'flex';
        
        fetch('/api/restart', {{ method: 'POST' }})
            .then(() => {{ setTimeout(() => {{ window.location.reload(); }}, 2000); }})
            .catch(err => {{ setTimeout(() => {{ window.location.reload(); }}, 2000); }});
    }}

    function addLog(msg, type = 'info') {{
        const logWindow = document.getElementById('logWindow');
        const div = document.createElement('div');
        div.className = `log-entry log-${{type}}`;
        div.innerText = `[${{new Date().toLocaleTimeString()}}] ${{msg}}`;
        logWindow.appendChild(div);
        logWindow.scrollTop = logWindow.scrollHeight;
    }}

    function clearLog() {{ document.getElementById('logWindow').innerHTML = ''; }}

    function toggleControls(active) {{
        isProcessing = active;
        document.getElementById('apiId').disabled = active;
        document.getElementById('apiHash').disabled = active;
        document.getElementById('enableProxy').disabled = active;
        document.getElementById('proxyFull').disabled = active;
        document.getElementById('proxyType').disabled = active;
        
        const loginGroup = document.getElementById('loginGroup');
        const stopGroup = document.getElementById('stopGroup');
        
        if(active) {{
            loginGroup.classList.add('d-none');
            stopGroup.classList.remove('d-none');
        }} else {{
            loginGroup.classList.remove('d-none');
            stopGroup.classList.add('d-none');
        }}
    }}

    // --- 倒计时逻辑 ---
    function startTimer(duration) {{
        clearInterval(timerInterval);
        let timer = duration;
        const display = document.getElementById('timerCount');
        const overlay = document.getElementById('qrOverlay');
        const timerDiv = document.getElementById('qrTimer');
        
        overlay.style.display = 'none';
        timerDiv.style.display = 'block';
        display.textContent = timer;

        timerInterval = setInterval(function () {{
            timer--;
            display.textContent = timer;

            if (timer <= 0) {{
                clearInterval(timerInterval);
                timerDiv.style.display = 'none';
                overlay.style.display = 'flex'; // 显示遮罩
                isProcessing = false; // 允许重新点击
            }}
        }}, 1000);
    }}

    function refreshQr() {{
        startLogin('qr');
    }}

    function startLogin(method) {{
        // 如果是刷新二维码，不需要检查 isProcessing
        
        clearLog();
        document.getElementById('qrContainer').style.display = 'none';
        document.getElementById('resultBox').style.display = 'none';
        document.getElementById('qrOverlay').style.display = 'none';
        
        // 自动解析代理字符串
        const proxyInput = document.getElementById('proxyFull').value.trim();
        const proxyType = document.getElementById('proxyType').value;
        let proxyIp = '';
        let proxyPort = '';

        if (document.getElementById('enableProxy').checked) {{
            if (!proxyInput.includes(':')) {{
                alert("代理地址格式错误，请使用 IP:端口 格式 (例如 127.0.0.1:7890)");
                return;
            }}
            const parts = proxyInput.split(':');
            proxyIp = parts[0];
            proxyPort = parts[1];
        }}
        
        const config = {{
            api_id: document.getElementById('apiId').value,
            api_hash: document.getElementById('apiHash').value,
            proxy_enabled: document.getElementById('enableProxy').checked,
            proxy_ip: proxyIp,
            proxy_port: proxyPort,
            proxy_type: proxyType,
            login_method: method
        }};

        if(!config.api_id || !config.api_hash) {{
            alert("请填写 API ID 和 API Hash");
            return;
        }}

        // 如果之前的 WS 还在，关闭它
        if(ws) ws.close();

        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        ws = new WebSocket(`${{protocol}}://${{window.location.host}}/ws`);

        ws.onopen = () => {{
            toggleControls(true);
            addLog("连接服务器成功...", "info");
            ws.send(JSON.stringify({{type: 'init', data: config}}));
        }};

        ws.onmessage = (event) => {{
            const msg = JSON.parse(event.data);
            handleMessage(msg);
        }};

        ws.onclose = () => {{
            addLog("连接已断开", "warning");
            toggleControls(false);
            clearInterval(timerInterval);
            hideInput();
        }};
        
        ws.onerror = (e) => {{
            addLog("连接错误", "error");
            toggleControls(false);
        }}
    }}

    function handleMessage(msg) {{
        switch(msg.type) {{
            case 'log':
                addLog(msg.text, msg.level);
                break;
            case 'qr_code':
                const img = document.getElementById('qrImage');
                img.src = "data:image/png;base64," + msg.data;
                document.getElementById('qrContainer').style.display = 'block';
                startTimer(55); // 稍微少于后端的60秒，提前显示遮罩
                addLog("二维码已生成，请扫描", "info");
                break;
            case 'qr_timeout':
                clearInterval(timerInterval);
                document.getElementById('qrTimer').style.display = 'none';
                document.getElementById('qrOverlay').style.display = 'flex';
                isProcessing = false; // 允许刷新
                break;
            case 'input_required':
                showInput(msg.prompt, msg.field_type);
                break;
            case 'session_generated':
                clearInterval(timerInterval); // 停止倒计时
                document.getElementById('qrContainer').style.display = 'none';
                document.getElementById('resultBox').style.display = 'block';
                
                document.getElementById('sessionText').innerText = msg.session;
                document.getElementById('serverPath').innerText = msg.filename;
                
                // 仅设置下载链接，不自动点击
                document.getElementById('downloadBtn').href = "/export/" + msg.filename;
                
                addLog("✅ 任务完成！文件已保存。", "success");
                ws.close();
                break;
            case 'error':
                addLog(msg.text, "error");
                break;
        }}
    }}

    function showInput(prompt, fieldType) {{
        const area = document.getElementById('inputArea');
        const input = document.getElementById('userInput');
        area.classList.remove('d-none');
        input.value = '';
        input.placeholder = prompt;
        input.type = fieldType === 'password' ? 'password' : 'text';
        input.focus();
        addLog(prompt, "warning");
    }}

    function hideInput() {{
        document.getElementById('inputArea').classList.add('d-none');
    }}

    function sendInput() {{
        const input = document.getElementById('userInput');
        const val = input.value.trim();
        if(!val) return;
        
        if(ws && ws.readyState === WebSocket.OPEN) {{
            ws.send(JSON.stringify({{type: 'input_response', data: val}}));
            addLog(`已发送: ******`, "info");
            hideInput();
        }}
    }}
    
    document.getElementById('userInput').addEventListener('keypress', function (e) {{
        if (e.key === 'Enter') sendInput();
    }});

    function stopProcess() {{
        if(ws) ws.close();
        addLog("用户手动停止任务", "warning");
        toggleControls(false);
        clearInterval(timerInterval);
    }}

    function copySession() {{
        const text = document.getElementById('sessionText').innerText;
        
        if (navigator.clipboard && window.isSecureContext) {{
            navigator.clipboard.writeText(text).then(() => {{
                alert('✅ 已复制到剪贴板!');
            }}).catch(() => fallbackCopy(text));
        }} else {{
            fallbackCopy(text);
        }}
    }}

    function fallbackCopy(text) {{
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-9999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {{
            document.execCommand('copy');
            alert('✅ 已复制到剪贴板!');
        }} catch (err) {{
            prompt("⚠️ 请手动复制:", text);
        }}
        document.body.removeChild(textArea);
    }}
</script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html_content)

# --------------------------
# 下载接口
# --------------------------
@app.get("/export/{filename}")
def download_file(filename: str):
    file_path = os.path.join(SESSIONS_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename, media_type='text/plain')
    return {"error": "File not found"}

# --------------------------
# 重启接口
# --------------------------
@app.post("/api/restart")
def restart_server():
    """触发服务器重启"""
    asyncio.create_task(shutdown_server())
    return JSONResponse(content={"status": "restarting"})

async def shutdown_server():
    """延迟1秒后退出进程，Docker会自动重启"""
    await asyncio.sleep(1)
    os._exit(0)

# --------------------------
# WebSocket 逻辑
# --------------------------

class SessionManager:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.client = None
    
    async def log(self, text, level="info"):
        await self.websocket.send_json({"type": "log", "text": text, "level": level})

    async def send_qr(self, url):
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        img_str = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        await self.websocket.send_json({"type": "qr_code", "data": img_str})

    async def request_input(self, prompt, field_type="text"):
        await self.websocket.send_json({"type": "input_required", "prompt": prompt, "field_type": field_type})
        data = await self.websocket.receive_json()
        if data.get('type') == 'input_response':
            return data.get('data')
        return None

    async def run(self, config):
        try:
            proxy = None
            if config.get('proxy_enabled', False):
                # 获取协议类型，默认为 socks5
                p_type = config.get('proxy_type', 'socks5')
                
                # 根据不同协议构建代理字典
                proxy = {
                    'proxy_type': p_type, # Telethon/Python-socks 接受 'socks5', 'socks4', 'http'
                    'addr': config['proxy_ip'],
                    'port': int(config['proxy_port']),
                }
                
                # SOCKS5 通常开启远程 DNS 解析
                if p_type == 'socks5':
                    proxy['rdns'] = True
                
                await self.log(f"使用代理: {p_type.upper()}://{config['proxy_ip']}:{config['proxy_port']}")
            else:
                await self.log("直连模式 (不使用代理)", "info")

            self.client = TelegramClient(
                StringSession(),
                int(config['api_id']),
                config['api_hash'],
                proxy=proxy,
                device_model="TG-Session-Web",
                system_version="Docker/Linux",
                app_version="1.0.0"
            )

            await self.client.connect()

            if not await self.client.is_user_authorized():
                if config['login_method'] == 'qr':
                    await self.handle_qr_login()
                else:
                    await self.handle_phone_login()
            
            string_session = self.client.session.save()
            me = await self.client.get_me()
            
            user_info = f"用户: {me.first_name} (@{me.username}) ID: {me.id}"
            await self.log(f"登录成功! {user_info}", "success")
            
            # 保存文件
            timestamp = int(time.time())
            filename = f"session_{me.id}_{timestamp}.txt"
            file_path = os.path.join(SESSIONS_DIR, filename)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(string_session)
            
            await self.websocket.send_json({
                "type": "session_generated", 
                "session": string_session,
                "file_path": filename,
                "filename": filename
            })

        except Exception as e:
            await self.log(f"操作中止或出错: {str(e)}", "error")
        finally:
            if self.client:
                await self.client.disconnect()

    async def handle_qr_login(self):
        try:
            qr_login = await self.client.qr_login()
            await self.log("正在生成二维码...", "info")
            await self.send_qr(qr_login.url)
            
            # 后端 60 秒超时控制
            try:
                await qr_login.wait(timeout=60)
            except asyncio.TimeoutError:
                await self.websocket.send_json({"type": "qr_timeout"})
                # raise Exception("二维码已过期") # 移除 Exception 以避免日志报错，由前端处理
                return # 结束流程
            except SessionPasswordNeededError:
                await self.handle_2fa()
                
        except Exception as e:
             raise e

    async def handle_phone_login(self):
        phone = await self.request_input("请输入手机号 (带区号 +86...):")
        if not phone: return
        
        await self.log(f"正在发送验证码到 {phone} ...")
        await self.client.send_code_request(phone)
        
        code = await self.request_input("请输入收到的验证码:")
        
        try:
            await self.client.sign_in(phone, code)
        except SessionPasswordNeededError:
            await self.handle_2fa()
        except PhoneCodeInvalidError:
            await self.log("验证码错误", "error")
            raise Exception("验证码错误")

    async def handle_2fa(self):
        await self.log("检测到两步验证密码", "warning")
        password = await self.request_input("请输入两步验证密码:", "password")
        await self.client.sign_in(password=password)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    manager = SessionManager(websocket)
    try:
        data = await websocket.receive_json()
        if data.get('type') == 'init':
            config = data.get('data')
            await manager.run(config)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WS Error: {e}")