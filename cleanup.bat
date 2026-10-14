@echo off
REM Remove Python cache files
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc
del /s /q *.pyo
del /s /q *.pyd

REM Remove development environment files
rmdir /s /q .idea
rmdir /s /q .vscode
rmdir /s /q venv
rmdir /s /q env
del /q .env
del /q .env.local

REM Remove distribution and build files
rmdir /s /q dist
rmdir /s /q build
rmdir /s /q *.egg-info
rmdir /s /q .eggs
rmdir /s /q .pytest_cache
del /q .coverage
rmdir /s /q htmlcov

REM Clean up Python cache
for /d /r . %%d in (.mypy_cache) do @if exist "%%d" rd /s /q "%%d"
for /d /r . %%d in (.pytest_cache) do @if exist "%%d" rd /s /q "%%d"

echo Cleanup completed!
