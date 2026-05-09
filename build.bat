@echo off
chcp 65001 >nul
echo ═══════════════════════════════════════════════
echo   KiroProManager - Nuitka Build
echo ═══════════════════════════════════════════════
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH
    pause
    exit /b 1
)

:: Check Nuitka
python -m nuitka --version >nul 2>&1
if errorlevel 1 (
    echo [*] Installing Nuitka...
    pip install nuitka ordered-set zstandard
)

:: Backup DB if exists in dist
set "DIST_DIR=dist\KiroProManager"
set "DB_BAK="
if exist "%DIST_DIR%\kiro_accounts.db" (
    copy /Y "%DIST_DIR%\kiro_accounts.db" "dist\kiro_accounts.db.bak" >nul
    set "DB_BAK=1"
    echo [*] DB backed up
)

:: Kill any running instance
taskkill /F /IM KiroProManager.exe >nul 2>&1

:: Clean old output
if exist "%DIST_DIR%" rd /s /q "%DIST_DIR%" >nul 2>&1
if exist "dist\main.dist" rd /s /q "dist\main.dist" >nul 2>&1

:: Get site-packages path
for /f "delims=" %%i in ('python -c "import site; print(site.getsitepackages()[1])"') do set "SITE_PKG=%%i"
echo [*] Site-packages: %SITE_PKG%

echo [*] Building with Nuitka (this may take several minutes)...
echo.

python -m nuitka ^
    --standalone ^
    --windows-console-mode=disable ^
    --output-dir=dist ^
    --output-filename=KiroProManager.exe ^
    --follow-imports ^
    --include-package=curl_cffi ^
    --include-package=playwright ^
    --include-package=playwright_stealth ^
    --include-package=cryptography ^
    --include-package=cffi ^
    --include-package=_cffi_backend ^
    --include-data-dir="%SITE_PKG%\playwright\driver"=playwright/driver ^
    --include-data-dir="%SITE_PKG%\playwright_stealth"=playwright_stealth ^
    --include-data-dir="%LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1217"=ms-playwright/chromium_headless_shell-1217 ^
    --include-data-dir="%LOCALAPPDATA%\ms-playwright\chromium-1217"=ms-playwright/chromium-1217 ^
    --enable-plugin=tk-inter ^
    --python-flag=no_docstrings ^
    --python-flag=-OO ^
    --python-flag=no_asserts ^
    --product-name=KiroProManager ^
    --product-version=1.0.0 ^
    --file-description="Kiro Pro Account Manager" ^
    --jobs=4 ^
    --assume-yes-for-downloads ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Nuitka build failed
    pause
    exit /b 1
)

:: Rename output
if exist "dist\main.dist" (
    if exist "%DIST_DIR%" rd /s /q "%DIST_DIR%"
    ren "dist\main.dist" "KiroProManager"
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
