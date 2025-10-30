cd..
echo Trying to uninstall 'yourpackagenamehere' in case it was installed.
REM pip uninstall -y yourpackagenamehere
REM pip install -e "%~dp0..."
pip install --upgrade -e .
rmdir /S /Q yourpackagenamehere.egg-info
rmdir /S /Q build
pause