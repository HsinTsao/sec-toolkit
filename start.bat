@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: Security Toolkit 启动脚本 (Windows)
:: 用法: start.bat [dev|prod|stop]

title Security Toolkit

:: 颜色定义 (Windows 10+)
set "GREEN=[92m"
set "CYAN=[96m"
set "YELLOW=[93m"
set "RED=[91m"
set "NC=[0m"

:: 项目目录
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

:: 显示 Banner
echo.
echo %CYAN%╔═══════════════════════════════════════════╗%NC%
echo %CYAN%║       🔐 Security Toolkit                 ║%NC%
echo %CYAN%║       安全工具库启动脚本                   ║%NC%
echo %CYAN%╚═══════════════════════════════════════════╝%NC%
echo.

if "%1"=="" goto :menu
if "%1"=="dev" goto :start_dev
if "%1"=="prod" goto :start_prod
if "%1"=="stop" goto :stop
if "%1"=="help" goto :help
goto :help

:menu
echo 请选择启动模式:
echo   1) 开发模式 (dev)
echo   2) 生产模式 (prod)
echo   3) 停止服务 (stop)
echo.
set /p choice="请输入选项 [1-3]: "

if "%choice%"=="1" goto :start_dev
if "%choice%"=="2" goto :start_prod
if "%choice%"=="3" goto :stop
echo %RED%[ERROR]%NC% 无效选项
goto :eof

:start_dev
echo %CYAN%[INFO]%NC% 启动开发环境...

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
pip install -q -r requirements.txt

start "Security Toolkit Backend" cmd /c "venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo %GREEN%[SUCCESS]%NC% 后端已启动

:: 启动前端
echo %CYAN%[INFO]%NC% 启动前端服务...
cd ..\frontend

if not exist "node_modules" (
    echo %CYAN%[INFO]%NC% 安装前端依赖...
    call npm install
)

start "Security Toolkit Frontend" cmd /c "npm run dev"
echo %GREEN%[SUCCESS]%NC% 前端已启动

cd ..
echo.
echo %GREEN%[SUCCESS]%NC% 开发环境启动完成！
echo.
echo   %GREEN%前端地址:%NC% http://localhost:5173
echo   %GREEN%后端地址:%NC% http://localhost:8000
echo   %GREEN%API 文档:%NC% http://localhost:8000/api/docs
echo.
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
docker-compose up -d --build

echo.
echo %GREEN%[SUCCESS]%NC% 生产环境启动完成！
echo.
echo   %GREEN%前端地址:%NC% http://localhost
echo   %GREEN%后端地址:%NC% http://localhost:8000
echo   %GREEN%API 文档:%NC% http://localhost:8000/api/docs
echo.
goto :eof

:stop
echo %CYAN%[INFO]%NC% 停止服务...

:: 停止 Docker 容器
docker-compose down 2>nul

:: 关闭开发环境窗口
taskkill /FI "WINDOWTITLE eq Security Toolkit*" /F >nul 2>nul

echo %GREEN%[SUCCESS]%NC% 所有服务已停止
goto :eof

:help
echo 用法: start.bat [命令]
echo.
echo 命令:
echo   dev     启动开发环境 (本地 Python + Node)
echo   prod    启动生产环境 (Docker)
echo   stop    停止所有服务
echo   help    显示帮助信息
echo.
echo 示例:
echo   start.bat dev    # 开发模式
echo   start.bat prod   # 生产模式
goto :eof

