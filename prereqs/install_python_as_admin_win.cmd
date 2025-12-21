:: Version 1.2.2
:: Download installer to %TEMP%, execute, then remove it (cleanup even on failure)
@echo off
setlocal

rem ============================================================
rem Arguments
rem   <PythonVersion>   Required. e.g. 3.12 or 3.12.10
rem   -l                List-only mode. Prints the resolved latest patch
rem                     version that has an available Windows installer and
rem                     exits without downloading/installing.
rem ============================================================

set "LIST_ONLY=0"
set "PYTHON_VERSION="

:ParseArgs
if "%~1"=="" goto ArgsDone
if /I "%~1"=="-l" (
    set "LIST_ONLY=1"
) else (
    if not defined PYTHON_VERSION (
        set "PYTHON_VERSION=%~1"
    ) else (
        echo Unknown argument: %~1
        echo Usage: %~nx0 ^<PythonVersion^> [-l]
        echo Example: %~nx0 3.12
        echo Example: %~nx0 3.12 -l
        exit /b 1
    )
)
shift
goto ParseArgs

:ArgsDone
rem Check if Python version is provided
if not defined PYTHON_VERSION (
    echo Usage: %~nx0 ^<PythonVersion^> [-l]
    echo Example: %~nx0 3.12
    echo Example: %~nx0 3.12 -l
    exit /b 1
)
rem ===== Parse requested version =====
for /f "tokens=1-3 delims=." %%A in ("%PYTHON_VERSION%") do (
    set "PV_MAJOR=%%A"
    set "PV_MINOR=%%B"
    set "PV_PATCH=%%C"
)

set "PYTHON_MAJOR_MINOR=%PV_MAJOR%.%PV_MINOR%"
call :Log Requested Python version: %PYTHON_MAJOR_MINOR%

rem ===== Decide target architecture (defaults to amd64) =====
set "ARCH=amd64"
if /I "%PROCESSOR_ARCHITECTURE%"=="x86" set "ARCH=x86"
if /I "%PROCESSOR_ARCHITEW6432%"=="x86" set "ARCH=amd64"

call :Log ARCHITECTURE: %ARCH%


rem ===== Work out LATEST_VERSION =====
if not "%PV_PATCH%"=="" (
    rem An exact patch was provided, e.g. 3.12.10
    set "LATEST_VERSION=%PV_MAJOR%.%PV_MINOR%.%PV_PATCH%"
    goto AfterVersion
)

goto FindLatestVersion

:AfterVersion
call :Log Provided version: %LATEST_VERSION%
goto Finalize

:FindLatestVersion
rem Find the latest patch version
call :Log Finding the latest patch version for Python %PYTHON_MAJOR_MINOR%...


:: Get the version.
for /f "usebackq delims=" %%I in (`^
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue';" ^
    "$url = 'https://www.python.org/ftp/python/';" ^
    "$page = Invoke-WebRequest -Uri $url;" ^
    "$versions = $page.Links | Where-Object { $_.href -match '^\d+\.\d+\.\d+/$' } | ForEach-Object { $_.href.TrimEnd('/') };" ^
    "$latest_version = ($versions | Where-Object { $_ -like '%PYTHON_MAJOR_MINOR%.*' }) | Sort-Object { [version]$_ } -Descending | Select-Object -First 1;" ^
    "Write-Output $latest_version"^
    `) do set "LATEST_VERSION=%%I"

rem Debug: Show the latest version
call :Log LATEST_VERSION: %LATEST_VERSION%

if "%LATEST_VERSION%"=="" (
    echo Failed to find the latest patch version for Python %PYTHON_MAJOR_MINOR%.
    exit /b 1
)

:Finalize
set "TARGET_DIR=C:\Python%PYTHON_MAJOR_MINOR:.=%"
call :Log TARGET INSTALLATION DIR: %TARGET_DIR%

rem Download the Python installer for the determined version
call :Log Fetching the installer for Python %LATEST_VERSION%...

rem ===== Ensure the resolved version has a Windows .exe installer; if not, walk patch down =====
set "CHECK_VERSION=%LATEST_VERSION%"
for /f "tokens=1-3 delims=." %%A in ("%CHECK_VERSION%") do (
    set "CV_MAJOR=%%A"
    set "CV_MINOR=%%B"
    set "CV_PATCH=%%C"
)

:ProbeInstaller
call :BuildInstallerUrl "%CHECK_VERSION%"
call :UrlExists "%INSTALLER_URL%"
if errorlevel 1 goto InstallerMissing

set "LATEST_VERSION=%CHECK_VERSION%"
call :Log Using installer for Python %LATEST_VERSION%
call :Log INSTALLER_URL: %INSTALLER_URL%
goto AfterInstallerResolve

:InstallerMissing
call :Log Installer not found for %CHECK_VERSION% (%INSTALLER_URL%)
if "%CV_PATCH%"=="" (
    echo Unable to determine patch version from "%CHECK_VERSION%".
    exit /b 1
)
if %CV_PATCH% LEQ 0 (
    echo No usable Windows .exe installer found for Python %PYTHON_MAJOR_MINOR%.
    exit /b 1
)
set /a CV_PATCH-=1
set "CHECK_VERSION=%CV_MAJOR%.%CV_MINOR%.%CV_PATCH%"
goto ProbeInstaller

:AfterInstallerResolve

rem In list-only mode, print ONLY the resolved version and exit.
if "%LIST_ONLY%"=="1" (
    echo %LATEST_VERSION%
    endlocal
    exit /b 0
)


rem ===== Use a temp-file installer path (download -> execute -> delete) =====
set "PYINSTALLER=%TEMP%\python-%LATEST_VERSION%-%ARCH%-installer.exe"
call :Log Installer path (TEMP): "%PYINSTALLER%"

if "%INSTALLER_URL%"=="" (
    echo Failed to retrieve the installer URL for Python %LATEST_VERSION%.
    exit /b 1
)

echo Downloading the installer from %INSTALLER_URL%...
echo To: "%PYINSTALLER%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%INSTALLER_URL%' -OutFile '%PYINSTALLER%'"
set "DL_RC=%ERRORLEVEL%"
if not "%DL_RC%"=="0" (
    echo Download failed with code %DL_RC%.
    if exist "%PYINSTALLER%" del /f /q "%PYINSTALLER%"
    endlocal
    exit /b %DL_RC%
)
if not exist "%PYINSTALLER%" (
    echo Download failed: installer file not found at "%PYINSTALLER%".
    endlocal
    exit /b 1
)

rem Install Python with specified switches
echo Installing Python %LATEST_VERSION%...
"%PYINSTALLER%" /passive InstallAllUsers=1 PrependPath=1 TargetDir="%TARGET_DIR%" AssociateFiles=1 InstallLauncherAllUsers=1
set "INSTALL_RC=%ERRORLEVEL%"

rem Clean up (always)
if exist "%PYINSTALLER%" del /f /q "%PYINSTALLER%"

if not "%INSTALL_RC%"=="0" (
    echo Python installer exited with code %INSTALL_RC%.
    endlocal
    exit /b %INSTALL_RC%
)

echo Python %LATEST_VERSION% installation completed.
endlocal
exit /b 0
:BuildInstallerUrl
set "INSTALLER_FILE=python-%~1.exe"
if /I "%ARCH%"=="amd64" set "INSTALLER_FILE=python-%~1-amd64.exe"
set "INSTALLER_URL=https://www.python.org/ftp/python/%~1/%INSTALLER_FILE%"
exit /b 0

:UrlExists
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue'; $u='%~1'; try { $r=Invoke-WebRequest -Uri $u -Method Head -UseBasicParsing; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400) { exit 0 } else { exit 1 } } catch { exit 1 }"
exit /b %ERRORLEVEL%

:Log
if "%LIST_ONLY%"=="0" echo %*
exit /b 0
