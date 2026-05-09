@echo off
chcp 65001 >nul
echo ═══════════════════════════════════════════════
echo   KiroProManager - PyInstaller Build
echo ═══════════════════════════════════════════════
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH
    pause
    exit /b 1
)

:: Check PyInstaller
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [*] Installing PyInstaller...
    pip install pyinstaller
)

:: Kill any running instance
taskkill /F /IM KiroProManager.exe >nul 2>&1

:: Backup DB if exists in dist
set "DIST_DIR=dist\KiroProManager"
set "DB_BAK="
if exist "%DIST_DIR%\kiro_accounts.db" (
    copy /Y "%DIST_DIR%\kiro_accounts.db" "dist\kiro_accounts.db.bak" >nul
    set "DB_BAK=1"
    echo [*] DB backed up
)

echo [*] Building with PyInstaller...
echo.

python build.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed
    pause
    exit /b 1
)

:: Restore DB
if defined DB_BAK (
    if exist "dist\kiro_accounts.db.bak" (
        copy /Y "dist\kiro_accounts.db.bak" "%DIST_DIR%\kiro_accounts.db" >nul
        echo [+] DB restored
    )
)

if exist "%DIST_DIR%\KiroProManager.exe" (
    echo.
    echo ═══════════════════════════════════════════════
    echo   Build successful!
    echo   Output: %DIST_DIR%\KiroProManager.exe
    echo ═══════════════════════════════════════════════
) else (
    echo.
    echo [ERROR] Build output not found
)

pause
