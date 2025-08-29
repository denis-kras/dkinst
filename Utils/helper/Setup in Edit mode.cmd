cd..
echo Trying to uninstall 'dkinst' in case it was installed.
REM pip uninstall -y dkinst
REM pip install -e "%~dp0..."
pip install --upgrade -e .
rmdir /S /Q dkinst.egg-info
rmdir /S /Q build
pause