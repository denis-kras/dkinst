@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Directory where this script lives (with trailing backslash)
set "SCRIPT_DIR=%~dp0"
REM Project root = parent folder of this script
set "ROOT=%SCRIPT_DIR%.."

REM ============================================================
REM Phase 1: Build executables
REM ============================================================

echo ============================================================
echo Checking for WSL
echo ============================================================
REM Check if WSL actually works by verifying the output of 'wsl echo ok'
REM (exit code is unreliable - returns 0 even without a distro)
set "WSL_OK="
for /f "usebackq delims=" %%O in (`wsl echo ok 2^>nul`) do set "WSL_OK=%%O"
if "!WSL_OK!"=="ok" goto :wsl_ready

echo WSL not ready. Trying to update...
wsl --update >nul 2>&1
set "WSL_OK="
for /f "usebackq delims=" %%O in (`wsl echo ok 2^>nul`) do set "WSL_OK=%%O"
if "!WSL_OK!"=="ok" goto :wsl_ready

echo Installing WSL with Ubuntu...
wsl --install -d Ubuntu --no-launch
if errorlevel 1 (
    echo ERROR: Failed to install WSL / Ubuntu.
    exit /b 1
)
echo Creating default user 'ubuntu'...
wsl -d Ubuntu bash -c "useradd -m -s /bin/bash -G sudo ubuntu && echo 'ubuntu:ubuntu' | chpasswd && echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/ubuntu"
if errorlevel 1 (
    echo ERROR: Failed to create default user.
    exit /b 1
)
ubuntu config --default-user ubuntu
set "WSL_OK="
for /f "usebackq delims=" %%O in (`wsl echo ok 2^>nul`) do set "WSL_OK=%%O"
if not "!WSL_OK!"=="ok" (
    echo WSL installed. Please restart your computer and re-run this script.
    exit /b 0
)

:wsl_ready
echo WSL is ready.

echo.
echo ============================================================
echo Checking for PyInstaller
echo ============================================================
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller.
        exit /b 1
    )
) else (
    echo PyInstaller is already installed.
)

echo.
echo ============================================================
echo Installing project in editable mode
echo ============================================================
pip install -e "%ROOT%"
if errorlevel 1 (
    echo ERROR: Failed to install project in editable mode.
    exit /b 1
)

echo.
echo ============================================================
echo Creating entry-point script
echo ============================================================
set "ENTRY=%TEMP%\dkinst_entry.py"
(
    echo from dkinst.cli import main
    echo import sys
    echo sys.exit(main^(^)^)
) > "%ENTRY%"

echo.
echo ============================================================
echo Building Windows executable
echo ============================================================
pyinstaller --onefile --console --clean --name dkinst --paths "%ROOT%" --distpath "%SCRIPT_DIR%." --specpath "%TEMP%" --workpath "%TEMP%\dkinst_pyinstaller_build" --collect-all dkinst "%ENTRY%"
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    del /f "%ENTRY%" >nul 2>&1
    exit /b 1
)

echo.
echo ============================================================
echo Cleanup (Windows build)
echo ============================================================
del /f "%ENTRY%" >nul 2>&1
if exist "%ROOT%\dkinst.egg-info" rmdir /s /q "%ROOT%\dkinst.egg-info"

echo.
echo Done. Windows executable is at: "%SCRIPT_DIR%dkinst.exe"

echo.
echo ============================================================
echo Building Ubuntu binary via WSL
echo ============================================================
REM Convert Windows paths to WSL paths
for /f "usebackq delims=" %%P in (`wsl wslpath -a "%ROOT%"`) do set "WSL_ROOT=%%P"
for /f "usebackq delims=" %%P in (`wsl wslpath -a "%SCRIPT_DIR%."`) do set "WSL_DIST=%%P"
REM Write a shell script to avoid cmd quoting issues
set "WSL_SCRIPT=%TEMP%\dkinst_wsl_build.sh"
(
    echo #!/bin/bash
    echo set -e
    echo sudo apt-get update
    echo sudo apt-get install -y --no-install-recommends python3 python3-pip python3-venv python3-dev binutils
    echo python3 -m venv /tmp/dkinst_venv
    echo source /tmp/dkinst_venv/bin/activate
    echo pip install pyinstaller
    echo pip install -e '!WSL_ROOT!'
    echo printf 'from dkinst.cli import main\nimport sys\nsys.exit^(main^(^)^)\n' ^> /tmp/dkinst_entry.py
    echo pyinstaller --onefile --console --clean --name dkinst --paths '!WSL_ROOT!' --distpath '!WSL_DIST!' --specpath /tmp --workpath /tmp/dkinst_pyinstaller_build --collect-all dkinst /tmp/dkinst_entry.py
) > "%WSL_SCRIPT%"
REM Convert script path, fix Windows CRLF line endings, and run it
for /f "usebackq delims=" %%P in (`wsl wslpath -a "%WSL_SCRIPT%"`) do set "WSL_SCRIPT_PATH=%%P"
wsl sed -i "s/\r$//" "!WSL_SCRIPT_PATH!"
wsl bash "!WSL_SCRIPT_PATH!"
if errorlevel 1 (
    del /f "%WSL_SCRIPT%" >nul 2>&1
    echo ERROR: WSL build failed.
    exit /b 1
)
del /f "%WSL_SCRIPT%" >nul 2>&1

echo.
echo ============================================================
echo Verifying Ubuntu binary
echo ============================================================
if not exist "%SCRIPT_DIR%dkinst" (
    echo ERROR: Ubuntu binary was not created at "%SCRIPT_DIR%dkinst"
    exit /b 1
)
powershell -NoProfile -Command "$b=[System.IO.File]::ReadAllBytes('%SCRIPT_DIR%dkinst')[0..3]; if($b[0]-eq 0x7F -and $b[1]-eq 0x45 -and $b[2]-eq 0x4C -and $b[3]-eq 0x46){Write-Host 'Verified: ELF binary'}else{Write-Host 'ERROR: Not an ELF binary';exit 1}"
if errorlevel 1 (
    echo ERROR: Ubuntu binary verification failed.
    exit /b 1
)

echo.
echo Done. Both executables are ready:
echo   Windows: "%SCRIPT_DIR%dkinst.exe"
echo   Ubuntu:  "%SCRIPT_DIR%dkinst"

REM ============================================================
REM Phase 2: Create GitHub release
REM ============================================================

echo.
echo ============================================================
echo Extracting version
echo ============================================================
for /f "delims=" %%v in ('python -c "import sys; sys.path.insert(0, r'%ROOT%'); from dkinst import __version__; print(__version__)"') do set "VERSION=%%v"
if not defined VERSION (
    echo ERROR: Could not extract version from dkinst/__init__.py
    exit /b 1
)
echo Version: %VERSION%

echo.
echo ============================================================
echo Checking gh CLI
echo ============================================================
where gh >nul 2>&1
if errorlevel 1 (
    echo gh CLI not found. Installing...
    winget install -e --id GitHub.cli --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo ERROR: Failed to install gh CLI.
        exit /b 1
    )
    REM Refresh PATH so gh is available in this session
    for /f "usebackq delims=" %%P in (`where /r "%ProgramFiles%\GitHub CLI" gh.exe 2^>nul`) do set "PATH=%%~dpP;!PATH!"
    where gh >nul 2>&1
    if errorlevel 1 (
        echo gh CLI installed but not found in PATH. Please restart your terminal and re-run.
        exit /b 1
    )
)
echo gh CLI found.

echo.
echo ============================================================
echo Creating zip files
echo ============================================================
set "WIN_ZIP=%SCRIPT_DIR%dkinst-%VERSION%-windows.zip"
set "UBU_ZIP=%SCRIPT_DIR%dkinst-%VERSION%-ubuntu.zip"

REM Remove old zips if they exist
del /f "%WIN_ZIP%" >nul 2>&1
del /f "%UBU_ZIP%" >nul 2>&1

powershell -NoProfile -Command "Compress-Archive -Path '%SCRIPT_DIR%dkinst.exe','%ROOT%\LICENSE' -DestinationPath '%WIN_ZIP%'"
if errorlevel 1 (
    echo ERROR: Failed to create Windows zip.
    exit /b 1
)
echo Created: dkinst-%VERSION%-windows.zip

powershell -NoProfile -Command "Compress-Archive -Path '%SCRIPT_DIR%dkinst','%ROOT%\LICENSE' -DestinationPath '%UBU_ZIP%'"
if errorlevel 1 (
    echo ERROR: Failed to create Ubuntu zip.
    exit /b 1
)
echo Created: dkinst-%VERSION%-ubuntu.zip

echo.
echo ============================================================
echo Creating git tag
echo ============================================================
git -C "%ROOT%" tag %VERSION% >nul 2>&1
if errorlevel 1 (
    echo Tag %VERSION% already exists, skipping.
) else (
    echo Created tag: %VERSION%
    git -C "%ROOT%" push origin %VERSION%
)

echo.
echo ============================================================
echo Creating GitHub release
echo ============================================================
pushd "%ROOT%"
gh release create %VERSION% "%WIN_ZIP%" "%UBU_ZIP%" --title "dkinst %VERSION%" --generate-notes
popd
if errorlevel 1 (
    echo ERROR: Failed to create GitHub release.
    del /f "%WIN_ZIP%" >nul 2>&1
    del /f "%UBU_ZIP%" >nul 2>&1
    exit /b 1
)

REM ============================================================
REM Phase 3: Cleanup
REM ============================================================

echo.
echo ============================================================
echo Cleanup
echo ============================================================
del /f "%WIN_ZIP%" >nul 2>&1
del /f "%UBU_ZIP%" >nul 2>&1
del /f "%SCRIPT_DIR%dkinst.exe" >nul 2>&1
del /f "%SCRIPT_DIR%dkinst" >nul 2>&1
echo Zip files and executables removed.

echo.
echo Done. GitHub release %VERSION% created successfully.
pause
