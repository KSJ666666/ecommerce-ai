@echo off
chcp 936 >nul
rem ============================================================
rem  按窗口标题停止 start_all.bat 拉起的四个服务
rem  只杀这四个窗口里的进程，不会动你 IDE 里跑的程序
rem ============================================================

echo 停止 客服服务 / 知识库服务 / spzx-order / spzx-product ...
taskkill /FI "WINDOWTITLE eq customer-service*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq knowledge-service*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq spzx-order*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq spzx-product*" /T /F >nul 2>&1
echo 完成。
timeout /t 2 >nul
