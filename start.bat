@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: Security Toolkit 启动脚本 (Windows)
:: 用法: start.bat [命令]

title Security Toolkit

:: 颜色定义
set "GREEN=[92m"
set "CYAN=[96m"
set "YELLOW=[93m"
set "RED=[91m"
set "BOLD=[1m"
set "NC=[0m"

:: 项目目录
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

:: 显示 Banner
:show_banner
echo.
echo %CYAN%╔═══════════════════════════════════════════╗%NC%
echo %CYAN%║       🔐 Security Toolkit                 ║%NC%
echo %CYAN%╚═══════════════════════════════════════════╝%NC%
echo.

if "%1"=="" goto :help
if "%1"=="dev" goto :start_dev
if "%1"=="run" goto :start_run
if "%1"=="prod" goto :start_prod
if "%1"=="stop" goto :stop
if "%1"=="status" goto :status
if "%1"=="sync-api" goto :sync_api
if "%1"=="help" goto :help
if "%1"=="-h" goto :help
if "%1"=="--help" goto :help
goto :unknown

:help
echo %BOLD%用法:%NC% start.bat ^<命令^>
echo.
echo %BOLD%启动命令:%NC%
echo   %GREEN%dev%NC%         启动开发环境 (后台运行)
echo   %GREEN%run%NC%         启动开发环境 (前台运行) %YELLOW%推荐%NC%
echo   %GREEN%prod%NC%        启动生产环境 (Docker)
echo.
echo %BOLD%管理命令:%NC%
echo   %GREEN%stop%NC%        停止所有服务
echo   %GREEN%status%NC%      查看服务运行状态
echo.
echo %BOLD%工具命令:%NC%
echo   %GREEN%sync-api%NC%    同步 API 类型 (后端 → 前端 TypeScript)
echo.
echo %BOLD%示例:%NC%
echo   start.bat run          # 开发模式 (前台)
echo   start.bat dev          # 开发模式 (后台)
echo   start.bat sync-api     # 同步 API 类型
echo.
echo %BOLD%数据目录:%NC%
echo   data/           数据库、日志文件
echo   backend/venv/   Python 虚拟环境
echo   frontend/node_modules/  Node.js 依赖
goto :eof

:unknown
echo %RED%[ERROR]%NC% 未知命令: %1
echo.
goto :help

:start_dev
echo %CYAN%[INFO]%NC% 启动开发环境 (后台)...

:: 创建数据目录
if not exist "data" mkdir data

:: 检查 Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %RED%[ERROR]%NC% Python 未安装
    goto :eof
)

:: 检查 Node
where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %RED%[ERROR]%NC% Node.js/npm 未安装
    goto :eof
)

:: 启动后端
echo %CYAN%[INFO]%NC% 启动后端服务...
cd backend

if not exist "venv" (
    echo %CYAN%[INFO]%NC% 创建 Python 虚拟环境...
    python -m venv venv
)

call venv\Scripts\activate.bat
echo %CYAN%[INFO]%NC% 安装 Python 依赖...
pip install -q -r requirements.txt

start "Toolkit-Backend" cmd /c "venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo %GREEN%[OK]%NC% 后端已启动

:: 启动前端
echo %CYAN%[INFO]%NC% 启动前端服务...
cd ..\frontend

if not exist "node_modules" (
    echo %CYAN%[INFO]%NC% 安装前端依赖...
    call npm install
)

start "Toolkit-Frontend" cmd /c "npm run dev"
echo %GREEN%[OK]%NC% 前端已启动

cd ..
echo.
echo %GREEN%[OK]%NC% 开发环境启动完成！
echo.
echo   %GREEN%前端:%NC% http://localhost:5173
echo   %GREEN%后端:%NC% http://localhost:8000
echo   %GREEN%文档:%NC% http://localhost:8000/api/docs
echo.
goto :eof

:start_run
echo %CYAN%[INFO]%NC% 启动开发环境 (前台)...

:: 创建数据目录
if not exist "data" mkdir data

:: 检查 Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %RED%[ERROR]%NC% Python 未安装
    goto :eof
)

:: 检查 Node
where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %RED%[ERROR]%NC% Node.js/npm 未安装
    goto :eof
)

:: 启动前端 (后台)
echo %CYAN%[INFO]%NC% 启动前端服务...
cd frontend

if not exist "node_modules" (
    echo %CYAN%[INFO]%NC% 安装前端依赖...
    call npm install
)

start "Toolkit-Frontend" cmd /c "npm run dev"
echo %GREEN%[OK]%NC% 前端已启动: http://localhost:5173

:: 启动后端 (前台)
echo %CYAN%[INFO]%NC% 启动后端服务 (前台模式)...
cd ..\backend

if not exist "venv" (
    echo %CYAN%[INFO]%NC% 创建 Python 虚拟环境...
    python -m venv venv
)

call venv\Scripts\activate.bat
echo %CYAN%[INFO]%NC% 安装 Python 依赖...
pip install -q -r requirements.txt

echo.
echo %CYAN%═══════════════════════════════════════════════════════════════%NC%
echo %GREEN%  后端实时日志 (Ctrl+C 停止)%NC%
echo %CYAN%═══════════════════════════════════════════════════════════════%NC%
echo   %GREEN%前端:%NC% http://localhost:5173
echo   %GREEN%后端:%NC% http://localhost:8000
echo   %GREEN%文档:%NC% http://localhost:8000/api/docs
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
goto :eof

:start_prod
echo %CYAN%[INFO]%NC% 启动生产环境 (Docker)...

:: 检查 Docker
where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %RED%[ERROR]%NC% Docker 未安装
    goto :eof
)

:: 创建数据目录
if not exist "data" mkdir data

:: 启动容器
docker compose up -d --build

echo.
echo %GREEN%[OK]%NC% 生产环境启动完成！
echo.
echo   %GREEN%前端:%NC% http://localhost
echo   %GREEN%后端:%NC% http://localhost:8000
echo   %GREEN%文档:%NC% http://localhost:8000/api/docs
echo.
goto :eof

:stop
echo %CYAN%[INFO]%NC% 停止服务...

:: 停止 Docker 容器
docker compose down 2>nul

:: 关闭开发环境窗口
taskkill /FI "WINDOWTITLE eq Toolkit-*" /F >nul 2>nul

echo %GREEN%[OK]%NC% 服务已停止
goto :eof

:status
echo.
echo %BOLD%服务状态:%NC%
:: 检查后端
tasklist /FI "WINDOWTITLE eq Toolkit-Backend" 2>nul | find "cmd.exe" >nul
if %ERRORLEVEL%==0 (
    echo   %GREEN%●%NC% 后端: 运行中
) else (
    echo   %RED%○%NC% 后端: 未运行
)
:: 检查前端
tasklist /FI "WINDOWTITLE eq Toolkit-Frontend" 2>nul | find "cmd.exe" >nul
if %ERRORLEVEL%==0 (
    echo   %GREEN%●%NC% 前端: 运行中
) else (
    echo   %RED%○%NC% 前端: 未运行
)
echo.
goto :eof

:sync_api
echo %CYAN%[INFO]%NC% 同步 API 类型...

:: 检查后端是否运行
curl -s http://localhost:8000/api/openapi.json >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %RED%[ERROR]%NC% 后端未运行，请先启动: start.bat dev
    goto :eof
)

:: 检查 npm
where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %RED%[ERROR]%NC% npm 未安装
    goto :eof
)

cd frontend

if not exist "node_modules" (
    echo %CYAN%[INFO]%NC% 安装前端依赖...
    call npm install
)

echo %CYAN%[INFO]%NC% 生成 TypeScript 客户端...
call npm run generate-api

if %ERRORLEVEL%==0 (
    echo %GREEN%[OK]%NC% API 类型同步完成！
    echo   %GREEN%位置:%NC% frontend/src/api/generated/
    echo   %GREEN%用法:%NC% import { getNotes, type Note } from '@/api'
) else (
    echo %RED%[ERROR]%NC% 生成失败
)

cd ..
goto :eof
