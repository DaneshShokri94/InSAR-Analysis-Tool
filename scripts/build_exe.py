import subprocess
import os

# Change to the directory containing Code.py
os.chdir('/mnt/c/Users/danes/Desktop/ice')

# Build command
cmd = [
    'pyinstaller',
    '--name=InSAR_SLC_Analyzer',
    '--onefile',
    '--windowed',
    '--icon=NONE',
    '--add-data=/home/danes/miniconda3/envs/isce2/lib/python3.11/site-packages/osgeo:osgeo',
    '--hidden-import=numpy',
    '--hidden-import=matplotlib',
    '--hidden-import=tkinter',
    '--hidden-import=osgeo',
    '--hidden-import=osgeo.gdal',
    '--collect-all=osgeo',
    '--collect-all=numpy',
    '--collect-all=matplotlib',
    'Code.py'
]

subprocess.run(cmd)