echo Trying to uninstall 'dkinst' in case it was installed.
pip uninstall -y dkinst
pip install "%~dp0."
REM python "%~dp0Setup.py" install
rmdir /S /Q dkinst.egg-info
rmdir /S /Q build
REM pause