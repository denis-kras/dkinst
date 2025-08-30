REM run this file in the same location as 'pyproject.toml'.
REM Install 'twine' library: pip install twine

cd..
REM Basic check.
python -m twine check --repository dkinst dist/*
pause
REM Upload the package.
python -m twine upload --repository dkinst dist/*
pause
