@echo off
chcp 936 >nul
setlocal
rem ============================================================
rem  一键启动：spzx 电商后端 -> 客服服务 -> 知识库服务
rem  依赖：JDK 17+、Maven、Nacos/MySQL/Redis/RabbitMQ 已启动
rem
rem  JDK 选择顺序：SPZX_JAVA_HOME > JAVA_HOME(需 17 以上) > 下面的默认路径
rem  其它路径均可通过同名环境变量覆盖（CS_PY / KB_PY / MVN）
rem ============================================================

set "ROOT=%~dp0"

set "DEFAULT_JAVA_HOME=D:\develop\Java\jdk-21"

if not "%SPZX_JAVA_HOME%"=="" set "JAVA_HOME=%SPZX_JAVA_HOME%"
if not exist "%JAVA_HOME%\bin\java.exe" set "JAVA_HOME=%DEFAULT_JAVA_HOME%"
rem 机器上 JAVA_HOME 常年指向 JDK8，这里探一下版本，1.8 直接换掉
if exist "%JAVA_HOME%\bin\java.exe" "%JAVA_HOME%\bin\java.exe" -version 2>&1 | findstr /C:"1.8." >nul
if not errorlevel 1 set "JAVA_HOME=%DEFAULT_JAVA_HOME%"

set "JAVA=%JAVA_HOME%\bin\java.exe"
if "%MVN%"=="" set "MVN=mvn"
if "%CS_PY%"=="" set "CS_PY=%ROOT%customer-service-backend\.venv\Scripts\python.exe"
if "%KB_PY%"=="" set "KB_PY=python"

set "ORDER_JAR=%ROOT%spzx-parent\spzx-modules\spzx-order\target\spzx-order.jar"
set "PRODUCT_JAR=%ROOT%spzx-parent\spzx-modules\spzx-product\target\spzx-product.jar"

echo.
echo ============================================================
echo   电商 AI 三方联调 启动脚本
echo   根目录: %ROOT%
echo   JDK   : %JAVA%
echo ============================================================

if not exist "%JAVA%" goto :no_java
if not exist "%CS_PY%" goto :no_cs_py
if not "%KB_PY%"=="python" if not exist "%KB_PY%" goto :no_kb_py

if not exist "%ORDER_JAR%" goto :build
if not exist "%PRODUCT_JAR%" goto :build
goto :start

:build
echo [信息] 未找到可执行 jar，先构建 spzx 订单/商品模块（首次较慢）...
pushd "%ROOT%spzx-parent"
call %MVN% -DskipTests -pl spzx-modules/spzx-order,spzx-modules/spzx-product -am package
popd
if not exist "%ORDER_JAR%" goto :build_failed

:start
echo [1/4] 启动 spzx-product  (9205)
start "spzx-product" /min "%JAVA%" -jar "%PRODUCT_JAR%" --server.port=9205

echo [2/4] 启动 spzx-order    (9207)
start "spzx-order" /min "%JAVA%" -jar "%ORDER_JAR%" --server.port=9207

echo       等待 Java 服务连上 Nacos（约 35 秒）...
ping -n 36 127.0.0.1 >nul

echo [3/4] 启动 客服服务      (18082)
start "customer-service" /min /d "%ROOT%customer-service-backend" "%CS_PY%" -m uvicorn app.api.app:app --host 127.0.0.1 --port 18082

echo [4/4] 启动 知识库服务-查询 (8001，加载 BGE 模型约 30 秒)
start "knowledge-service" /min /d "%ROOT%knowledge-service" "%KB_PY%" -m uvicorn knowledge.api.query_router:create_app --factory --host 127.0.0.1 --port 8001

echo.
echo 四个服务已各自在独立窗口启动（窗口标题即服务名）。
echo 自检: python verify_e2e.py          快速检查
echo       python verify_e2e.py --full   端到端对话
echo 停止: 双击 stop_all.bat
echo.
pause
exit /b 0

:no_java
echo [错误] 找不到 java: %JAVA%
echo        请设置 SPZX_JAVA_HOME 指向 JDK 17 及以上版本。
pause
exit /b 1

:no_cs_py
echo [错误] 找不到客服虚拟环境: %CS_PY%
echo        请先执行:
echo          cd customer-service-backend
echo          python -m venv .venv
echo          .venv\Scripts\pip install -r requirements.txt
pause
exit /b 1

:no_kb_py
echo [错误] 找不到知识库服务的 Python: %KB_PY%
echo        请先创建 conda 环境并安装 knowledge\requirements.txt，再设置 KB_PY 指向该环境的 python.exe。
pause
exit /b 1

:build_failed
echo [错误] 构建失败，请手动执行:
echo        cd spzx-parent
echo        mvn -DskipTests -pl spzx-modules/spzx-order,spzx-modules/spzx-product -am package
pause
exit /b 1
