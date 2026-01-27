# Building Windows Executable

This guide explains how to create a standalone `.exe` file from the InSAR Toolkit.

## Prerequisites

- Windows 10/11 (64-bit)
- Python 3.10 or 3.11
- Anaconda or Miniconda

## Quick Build

### Step 1: Create Environment

```bash
conda create -n insar_app python=3.10 -y
conda activate insar_app
pip install numpy matplotlib rasterio pyinstaller
```

### Step 2: Build Executable

```bash
cd insar-toolkit
pyinstaller --onefile --windowed --name "ASF_InSAR_Viewer" src/ASF_InSAR_Viewer_Standalone.py
```

### Step 3: Find Your EXE

The executable will be at: `dist/ASF_InSAR_Viewer.exe`

---

## Comprehensive Build (with all dependencies)

If the basic build fails, use this command:

```bash
pyinstaller --onefile --windowed --name "ASF_InSAR_Viewer" ^
    --collect-all rasterio ^
    --hidden-import numpy ^
    --hidden-import matplotlib ^
    --hidden-import matplotlib.backends.backend_tkagg ^
    --hidden-import rasterio ^
    --hidden-import rasterio.sample ^
    --hidden-import rasterio._shim ^
    --hidden-import tkinter ^
    src/ASF_InSAR_Viewer_Standalone.py
```

---

## Troubleshooting

### Intel MKL Error
```
pip uninstall numpy
pip install numpy
```

### Missing Libraries
Build with console to see errors:
```bash
pyinstaller --onefile --console --name "Debug" src/ASF_InSAR_Viewer_Standalone.py
```

### Large File Size
Exclude unused modules:
```bash
pyinstaller --onefile --exclude-module scipy --exclude-module pandas ...
```

---

## Code Protection Options

| Method | Protection Level | Notes |
|--------|-----------------|-------|
| PyInstaller | Low | Code can be extracted |
| PyArmor | Medium | Obfuscation |
| Nuitka | High | Compiles to C |

For commercial distribution, consider using Nuitka or PyArmor.
