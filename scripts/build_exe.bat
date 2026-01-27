@echo off
echo ============================================
echo   ASF InSAR Viewer - EXE Builder
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/4] Installing required packages...
pip install pyinstaller numpy matplotlib rasterio --quiet

echo.
echo [2/4] Checking installation...
python -c "import numpy; import matplotlib; import rasterio; print('All packages OK')"
if errorlevel 1 (
    echo ERROR: Package installation failed!
    pause
    exit /b 1
)

echo.
echo [3/4] Building executable (this may take 2-5 minutes)...
pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name "ASF_InSAR_Viewer" ^
    --add-data "C:\Users\danes\Desktop\ice\ASF_InSAR_Viewer_Standalone.py;." ^
    --hidden-import numpy ^
    --hidden-import matplotlib ^
    --hidden-import matplotlib.backends.backend_tkagg ^
    --hidden-import rasterio ^
    --hidden-import rasterio.sample ^
    --hidden-import rasterio._shim ^
    --hidden-import rasterio.control ^
    --hidden-import rasterio.crs ^
    --hidden-import rasterio.vrt ^
    --collect-all rasterio ^
    ASF_InSAR_Viewer_Standalone.py

echo.
echo [4/4] Cleaning up...

if exist "dist\ASF_InSAR_Viewer.exe" (
    echo.
    echo ============================================
    echo   SUCCESS! 
    echo ============================================
    echo.
    echo Your executable is ready at:
    echo   dist\ASF_InSAR_Viewer.exe
    echo.
    echo You can copy this .exe file to any Windows
    echo computer and run it without Python!
    echo.
) else (
    echo.
    echo ERROR: Build failed! Check the output above.
)

pause
