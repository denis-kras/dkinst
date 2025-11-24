:: Version 1.0.4
:: Fixed micro verson download
@echo off
setlocal

rem Check if Python version is provided
if "%~1"=="" (
    echo Usage: %0 ^<PythonVersion^>
    echo Example: %0 3.12
    exit /b 1
)

set "PYINSTALLER=%~dp0python_installer.exe"

rem ===== Parse requested version =====
set "PYTHON_VERSION=%~1"
for /f "tokens=1-3 delims=." %%A in ("%PYTHON_VERSION%") do (
    set "PV_MAJOR=%%A"
    set "PV_MINOR=%%B"
    set "PV_PATCH=%%C"
)

set "PYTHON_MAJOR_MINOR=%PV_MAJOR%.%PV_MINOR%"
echo Requested Python version: %PYTHON_MAJOR_MINOR%

rem ===== Decide target architecture (defaults to amd64) =====
set "ARCH=amd64"
if /I "%PROCESSOR_ARCHITECTURE%"=="x86" set "ARCH=x86"
if /I "%PROCESSOR_ARCHITEW6432%"=="x86" set "ARCH=amd64"

echo ARCHITECTURE: %ARCH%


rem ===== Work out LATEST_VERSION =====
if not "%PV_PATCH%"=="" (
    rem An exact patch was provided, e.g. 3.12.10
    set "LATEST_VERSION=%PV_MAJOR%.%PV_MINOR%.%PV_PATCH%"
    goto AfterVersion
)

goto FindLatestVersion

:AfterVersion
echo Provided version: %LATEST_VERSION%
goto Finalize

:FindLatestVersion
rem Find the latest patch version
echo Finding the latest patch version for Python %PYTHON_MAJOR_MINOR%...

:: This is the same as the next, but without the for loop. Since if there will be an exception, we will not get it with for.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $mm='%PYTHON_MAJOR_MINOR%'; $maj,$min=$mm -split '\.'; $html=(Invoke-WebRequest 'https://www.python.org/ftp/python/').Content; $rx=[regex]'href=""(?:/ftp/python/)?(\d+)\.(\d+)\.(\d+)/""'; $vers=foreach($m in $rx.Matches($html)){[version]::Parse(($m.Groups[1].Value+'.'+$m.Groups[2].Value+'.'+$m.Groups[3].Value))}; ($vers|?{$_.Major -eq [int]$maj -and $_.Minor -eq [int]$min}|sort -desc|select -f 1).ToString()"

:: Get the version.
for /f "usebackq delims=" %%I in (`^
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$url = 'https://www.python.org/ftp/python/';" ^
    "$page = Invoke-WebRequest -Uri $url;" ^
    "$versions = $page.Links | Where-Object { $_.href -match '^\d+\.\d+\.\d+/$' } | ForEach-Object { $_.href.TrimEnd('/') };" ^
    "$latest_version = ($versions | Where-Object { $_ -like '%PYTHON_MAJOR_MINOR%.*' }) | Sort-Object { [version]$_ } -Descending | Select-Object -First 1;" ^
    "Write-Output $latest_version"^
    `) do set "LATEST_VERSION=%%I"

rem Debug: Show the latest version
echo LATEST_VERSION: %LATEST_VERSION%

if "%LATEST_VERSION%"=="" (
    echo Failed to find the latest patch version for Python %PYTHON_MAJOR_MINOR%.
    exit /b 1
)

:Finalize
set "TARGET_DIR=C:\Python%LATEST_VERSION:.=%"
echo TARGET INSTALLATION DIR: %TARGET_DIR%

rem Download the Python installer for the determined version
echo Fetching the installer for Python %LATEST_VERSION%...

rem Decide installer file name based on architecture
set "INSTALLER_FILE=python-%LATEST_VERSION%.exe"
if /I "%ARCH%"=="amd64" set "INSTALLER_FILE=python-%LATEST_VERSION%-amd64.exe"

set "INSTALLER_URL=https://www.python.org/ftp/python/%LATEST_VERSION%/%INSTALLER_FILE%"

echo INSTALLER_URL: %INSTALLER_URL%

if "%INSTALLER_URL%"=="%INSTALLER_URL:.exe=%" (
    echo No ".exe" found in INSTALLER_URL.
    echo Try using the installer again by providing the lower exact version, eg. 3.12.10.
    exit /b 1
) else (
    echo ".exe" found in INSTALLER_URL
)

if "%INSTALLER_URL%"=="" (
    echo Failed to retrieve the installer URL for Python %LATEST_VERSION%.
    exit /b 1
)

echo Downloading the installer from %INSTALLER_URL%...
echo To: "%PYINSTALLER%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri %INSTALLER_URL% -OutFile '%PYINSTALLER%'"

rem Install Python with specified switches
echo Installing Python %LATEST_VERSION%...
"%PYINSTALLER%" /passive InstallAllUsers=1 PrependPath=1 TargetDir="%TARGET_DIR%" AssociateFiles=1 InstallLauncherAllUsers=1

rem Clean up
del "%PYINSTALLER%"

echo Python %LATEST_VERSION% installation completed.
endlocal
exit /b 0