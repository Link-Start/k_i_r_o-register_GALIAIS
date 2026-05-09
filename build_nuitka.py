#!/usr/bin/env python3
"""
Nuitka build script for KiroProManager.
Compiles Python to C -> native binary, making reverse engineering extremely difficult.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
import site

# Paths
PROJECT_DIR = Path(__file__).parent
MAIN_PY = PROJECT_DIR / "main.py"
DIST_DIR = PROJECT_DIR / "dist" / "KiroProManager"
DB_FILE = "kiro_accounts.db"

site_packages = Path(site.getsitepackages()[1])
browsers_dir = Path.home() / "AppData" / "Local" / "ms-playwright"

# Backup DB before build
db_backup = None
db_in_dist = DIST_DIR / DB_FILE
if db_in_dist.exists():
    db_backup = PROJECT_DIR / "dist" / f"{DB_FILE}.bak"
    shutil.copy2(db_in_dist, db_backup)
    print(f"[*] DB backed up: {db_backup}")

# Build Nuitka command
cmd = [
    sys.executable, "-m", "nuitka",
    "--standalone",
    "--windows-console-mode=disable",
    f"--output-dir={PROJECT_DIR / 'dist'}",
    "--output-filename=KiroProManager.exe",
    # Follow imports for all needed packages
    "--follow-imports",
    # Include required packages (compiled to C)
    "--include-package=curl_cffi",
    "--include-package=playwright",
    "--include-package=playwright_stealth",
    "--include-package=cryptography",
    "--include-package=cffi",
    "--include-package=_cffi_backend",
    # Include data files: playwright driver (node binary + scripts)
    f"--include-data-dir={site_packages / 'playwright' / 'driver'}=playwright/driver",
    # Include data files: playwright_stealth JS files
    f"--include-data-dir={site_packages / 'playwright_stealth'}=playwright_stealth",
    # Include browsers
    f"--include-data-dir={browsers_dir / 'chromium_headless_shell-1217'}=ms-playwright/chromium_headless_shell-1217",
    f"--include-data-dir={browsers_dir / 'chromium-1217'}=ms-playwright/chromium-1217",
    # Plugins
    "--enable-plugin=tk-inter",
    # Disable debug/traceback info for better obfuscation
    "--python-flag=no_docstrings",
    "--python-flag=-OO",
    # Remove assert statements
    "--python-flag=no_asserts",
    # Company info
    "--product-name=KiroProManager",
    "--product-version=1.0.0",
    "--file-description=Kiro Pro Account Manager",
    # Performance
    "--jobs=4",
    # Auto-accept downloads (dependency walker, etc.)
    "--assume-yes-for-downloads",
    # Main script
    str(MAIN_PY),
]

print("[*] Building with Nuitka (this will take several minutes)...")
print(f"[*] Command: {' '.join(cmd[:10])}...")
print()

env = os.environ.copy()
env["NUITKA_ASSUME_YES_FOR_DOWNLOADS"] = "1"
result = subprocess.run(cmd, cwd=str(PROJECT_DIR), env=env)

if result.returncode != 0:
    print(f"\n[!] Build failed with code {result.returncode}")
    sys.exit(1)

# Nuitka outputs to dist/main.dist/ by default, rename to KiroProManager
nuitka_out = PROJECT_DIR / "dist" / "main.dist"
if nuitka_out.exists():
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    nuitka_out.rename(DIST_DIR)
    print(f"[+] Renamed {nuitka_out} -> {DIST_DIR}")

# Restore DB
if db_backup and db_backup.exists():
    shutil.copy2(db_backup, DIST_DIR / DB_FILE)
    print(f"[+] DB restored: {DIST_DIR / DB_FILE}")

print(f"\n[+] Build complete: {DIST_DIR / 'KiroProManager.exe'}")
