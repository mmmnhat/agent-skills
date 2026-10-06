@echo off
chcp 65001 >NUL
title Cai dat scene_cut (chi chay 1 lan)
cd /d "%~dp0"
set "PY="
py -3 --version >NUL 2>NUL && set "PY=py -3"
if not defined PY python --version >NUL 2>NUL && set "PY=python"
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY="%%D\python.exe""
if not defined PY (
  echo Chua co Python - dang cai bang winget...
  winget install -e --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements
  for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY="%%D\python.exe""
)
if not defined PY (echo [LOI] Khong cai duoc Python. Tai tai python.org roi chay lai file nay. & pause & exit /b 1)
echo Python: %PY%
%PY% "%~dp0scene_cut.py" check
if errorlevel 1 (echo [LOI] Kiem tra requirements that bai - chup man hinh gui Claude. & pause & exit /b 1)
%PY% -c "import sys,os;print(sys.executable)" > "%~dp0_python_path.txt"
start "scene_cut" /min %PY% "%~dp0scene_cut.py" serve --install-startup
echo.
echo ==============================================
echo  XONG. Dich vu da chay nen va tu bat khi mo may.
echo  Tu gio chi can dan duong dan video cho Claude.
echo ==============================================
pause
