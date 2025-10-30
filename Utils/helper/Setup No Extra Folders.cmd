echo Trying to uninstall 'yourpackagenamehere' in case it was installed.
pip uninstall -y yourpackagenamehere
pip install "%~dp0."
REM python "%~dp0Setup.py" install
rmdir /S /Q yourpackagenamehere.egg-info
rmdir /S /Q build
REM pause