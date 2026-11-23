@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
where py >nul 2>nul
if not errorlevel 1 goto use_py
where python >nul 2>nul
if not errorlevel 1 goto use_python
echo Python 3.9+ was not found. Install Python and retry. 1>&2
exit /b 2

:use_py
py -3 "%SCRIPT_DIR%bootstrap.py" %*
exit /b %errorlevel%

:use_python
python "%SCRIPT_DIR%bootstrap.py" %*
exit /b %errorlevel%
