"""
Land Subsidence Analysis Tool
=============================
Comprehensive InSAR displacement analysis for land subsidence monitoring.
Supports time series analysis, GIS export, and report generation.

Author: Danesh Shokri
Version: 1.0
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle, Circle
import os
import glob
import json
from datetime import datetime, date
import re
import threading
import subprocess
import xml.etree.ElementTree as ET
from queue import Queue

# Try to import required libraries
try:
    from osgeo import gdal, osr, ogr
    gdal.UseExceptions()
    HAS_GDAL = True
except ImportError:
    HAS_GDAL = False

try:
    import rasterio
    from rasterio.transform import rowcol
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

try:
    import h5py
    HAS_H5PY = True
except ImportError:
    HAS_H5PY = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

try:
    import asf_search as asf
    HAS_ASF = True
except ImportError:
    HAS_ASF = False


class LandSubsidenceAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("Land Subsidence Analysis Tool v1.0")
        self.root.geometry("1700x1000")
        self.root.minsize(1400, 900)

        # Color scheme
        self.colors = {
            'bg_dark': '#1a1a2e',
            'bg_medium': '#16213e',
            'bg_light': '#0f3460',
            'accent': '#e94560',
            'accent_hover': '#ff6b6b',
            'text': '#ffffff',
            'text_secondary': '#a0a0a0',
            'success': '#00d9a5',
            'warning': '#ffc107',
            'border': '#2d3748',
            'subsidence': '#ff4444',
            'uplift': '#4444ff'
        }

        self.root.configure(bg=self.colors['bg_dark'])

        # Variables
        self.folder_path = tk.StringVar()
        self.status_var = tk.StringVar(value="Welcome! Load InSAR displacement data to begin analysis.")

        # Data storage
        self.displacement_files = []  # List of (date_pair, filepath, data, transform)
        self.current_data = None
        self.current_transform = None
        self.current_crs = None
        self.dem_data = None
        self.coherence_data = None

        # Analysis points/regions
        self.analysis_points = []  # List of (x, y, name) in pixel coordinates
        self.analysis_regions = []  # List of (x1, y1, x2, y2, name)

        # Time series data
        self.time_series_data = {}  # {point_name: [(date, displacement), ...]}

        # Click mode
        self.click_mode = tk.StringVar(value="none")  # none, point, region
        self.region_start = None

        # Custom colormaps
        self.displacement_cmap = self.create_displacement_colormap()

        # ASF Download & ISCE2 Processing variables
        self.earthdata_user = tk.StringVar()
        self.earthdata_pass = tk.StringVar()
        self.aoi_lat_min = tk.StringVar()
        self.aoi_lat_max = tk.StringVar()
        self.aoi_lon_min = tk.StringVar()
        self.aoi_lon_max = tk.StringVar()
        self.search_start_date = tk.StringVar(value="2024-01-01")
        self.search_end_date = tk.StringVar(value="2024-12-31")
        self.track_number = tk.StringVar()
        self.flight_direction = tk.StringVar(value="ASCENDING")
        self.conda_env = tk.StringVar(value="isce2")

        # ASF search results and processing state
        self.asf_search_results = []
        self.selected_pair_indices = []
        self.download_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "InSAR_Processing"))
        self.processing_thread = None
        self.download_thread = None
        self.is_processing = False
        self.is_downloading = False

        self.setup_styles()
        self.create_widgets()
        self.check_dependencies()

    def create_displacement_colormap(self):
        """Create custom colormap for displacement (blue=uplift, red=subsidence)"""
        colors_list = [
            '#0000ff', '#4444ff', '#8888ff', '#ccccff',
            '#ffffff',
            '#ffcccc', '#ff8888', '#ff4444', '#ff0000'
        ]
        return LinearSegmentedColormap.from_list('displacement', colors_list, N=256)

    def check_dependencies(self):
        """Check and report missing dependencies"""
        missing = []
        if not HAS_GDAL and not HAS_RASTERIO:
            missing.append("GDAL or rasterio (for reading GeoTIFFs)")
        if not HAS_H5PY:
            missing.append("h5py (for HDF5 time series)")
        if not HAS_REPORTLAB:
            missing.append("reportlab (for PDF reports)")

        if missing:
            msg = "Optional dependencies not found:\n\n"
            msg += "\n".join(f"  - {m}" for m in missing)
            msg += "\n\nSome features may be limited."
            messagebox.showinfo("Dependencies", msg)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Dark.TFrame', background=self.colors['bg_dark'])
        style.configure('Title.TLabel', background=self.colors['bg_dark'],
                       foreground=self.colors['text'], font=('Segoe UI', 20, 'bold'))
        style.configure('Status.TLabel', background=self.colors['bg_light'],
                       foreground=self.colors['text'], font=('Segoe UI', 9), padding=10)
        style.configure("Custom.Horizontal.TProgressbar",
                       background=self.colors['accent'], troughcolor=self.colors['bg_light'])

    def create_widgets(self):
        main_container = ttk.Frame(self.root, style='Dark.TFrame')
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Header
        header_frame = ttk.Frame(main_container, style='Dark.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(header_frame, text="Land Subsidence Analysis Tool",
                 style='Title.TLabel').pack(side=tk.LEFT)

        # Main content area
        content_frame = ttk.Frame(main_container, style='Dark.TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Left Panel (Controls)
        left_panel = ttk.Frame(content_frame, style='Dark.TFrame', width=350)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left_panel.pack_propagate(False)

        self.create_data_card(left_panel)
        self.create_download_card(left_panel)
        self.create_analysis_card(left_panel)
        self.create_points_card(left_panel)
        self.create_export_card(left_panel)

        # Right Panel (Visualization)
        right_panel = ttk.Frame(content_frame, style='Dark.TFrame')
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Displacement Map
        self.map_frame = ttk.Frame(self.notebook, style='Dark.TFrame')
        self.notebook.add(self.map_frame, text='  Displacement Map  ')
        self.create_map_tab(self.map_frame)

        # Tab 2: Time Series
        self.ts_frame = ttk.Frame(self.notebook, style='Dark.TFrame')
        self.notebook.add(self.ts_frame, text='  Time Series  ')
        self.create_timeseries_tab(self.ts_frame)

        # Tab 3: Statistics
        self.stats_frame = ttk.Frame(self.notebook, style='Dark.TFrame')
        self.notebook.add(self.stats_frame, text='  Statistics  ')
        self.create_stats_tab(self.stats_frame)

        # Status Bar
        status_frame = ttk.Frame(self.root, style='Dark.TFrame')
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(status_frame, textvariable=self.status_var,
                 style='Status.TLabel').pack(fill=tk.X)

    def create_card(self, parent, title):
        card = tk.Frame(parent, bg=self.colors['bg_medium'],
                       highlightbackground=self.colors['border'], highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 10))

        header = tk.Frame(card, bg=self.colors['bg_light'], height=35)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=title, bg=self.colors['bg_light'],
                fg=self.colors['text'], font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=12, pady=6)

        body = tk.Frame(card, bg=self.colors['bg_medium'])
        body.pack(fill=tk.X, padx=12, pady=12)
        return body

    def create_data_card(self, parent):
        body = self.create_card(parent, "DATA INPUT")

        # Folder selection
        tk.Label(body, text="InSAR Products Folder:", bg=self.colors['bg_medium'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(anchor=tk.W)

        folder_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        folder_frame.pack(fill=tk.X, pady=(5, 10))

        tk.Entry(folder_frame, textvariable=self.folder_path,
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT,
                font=('Segoe UI', 8)).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)

        tk.Button(folder_frame, text="Browse", bg=self.colors['accent'],
                 fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 8, 'bold'),
                 command=self.browse_folder).pack(side=tk.RIGHT, padx=(5, 0), ipadx=10, ipady=3)

        # Load buttons
        btn_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        btn_frame.pack(fill=tk.X, pady=(5, 0))

        tk.Button(btn_frame, text="Load Displacement", bg=self.colors['success'],
                 fg=self.colors['bg_dark'], relief=tk.FLAT, font=('Segoe UI', 9, 'bold'),
                 command=self.load_displacement_data).pack(fill=tk.X, ipady=8)

        tk.Button(btn_frame, text="Load HDF5 Time Series", bg=self.colors['bg_light'],
                 fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 9),
                 command=self.load_hdf5_timeseries).pack(fill=tk.X, ipady=6, pady=(5, 0))

        # File list
        self.file_listbox = tk.Listbox(body, height=5, bg=self.colors['bg_light'],
                                       fg=self.colors['text'], selectbackground=self.colors['accent'],
                                       relief=tk.FLAT, font=('Consolas', 8))
        self.file_listbox.pack(fill=tk.X, pady=(10, 0))
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_select)

    def create_download_card(self, parent):
        """Create ASF Download & ISCE2 Processing card"""
        body = self.create_card(parent, "ASF DOWNLOAD & PROCESS")

        if not HAS_ASF:
            tk.Label(body, text="Install asf_search:\npip install asf_search",
                    bg=self.colors['bg_medium'], fg=self.colors['warning'],
                    font=('Segoe UI', 9)).pack(anchor=tk.W)
            return

        # Credentials section
        tk.Label(body, text="NASA Earthdata Credentials:", bg=self.colors['bg_medium'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(anchor=tk.W)

        cred_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        cred_frame.pack(fill=tk.X, pady=(3, 5))

        tk.Label(cred_frame, text="User:", bg=self.colors['bg_medium'],
                fg=self.colors['text'], font=('Segoe UI', 8), width=5).pack(side=tk.LEFT)
        tk.Entry(cred_frame, textvariable=self.earthdata_user,
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT,
                font=('Segoe UI', 8), width=12).pack(side=tk.LEFT, padx=(0, 5), ipady=3)

        tk.Label(cred_frame, text="Pass:", bg=self.colors['bg_medium'],
                fg=self.colors['text'], font=('Segoe UI', 8), width=5).pack(side=tk.LEFT)
        tk.Entry(cred_frame, textvariable=self.earthdata_pass, show="*",
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT,
                font=('Segoe UI', 8), width=12).pack(side=tk.LEFT, ipady=3)

        # Area of Interest
        tk.Label(body, text="Area of Interest (Lat/Lon):", bg=self.colors['bg_medium'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(5, 0))

        aoi_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        aoi_frame.pack(fill=tk.X, pady=(3, 5))

        tk.Label(aoi_frame, text="Lat:", bg=self.colors['bg_medium'],
                fg=self.colors['text'], font=('Segoe UI', 8)).pack(side=tk.LEFT)
        tk.Entry(aoi_frame, textvariable=self.aoi_lat_min, width=8,
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT,
                font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=(2, 2), ipady=3)
        tk.Label(aoi_frame, text="to", bg=self.colors['bg_medium'],
                fg=self.colors['text'], font=('Segoe UI', 8)).pack(side=tk.LEFT)
        tk.Entry(aoi_frame, textvariable=self.aoi_lat_max, width=8,
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT,
                font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=(2, 0), ipady=3)

        aoi_frame2 = tk.Frame(body, bg=self.colors['bg_medium'])
        aoi_frame2.pack(fill=tk.X, pady=(0, 5))

        tk.Label(aoi_frame2, text="Lon:", bg=self.colors['bg_medium'],
                fg=self.colors['text'], font=('Segoe UI', 8)).pack(side=tk.LEFT)
        tk.Entry(aoi_frame2, textvariable=self.aoi_lon_min, width=8,
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT,
                font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=(2, 2), ipady=3)
        tk.Label(aoi_frame2, text="to", bg=self.colors['bg_medium'],
                fg=self.colors['text'], font=('Segoe UI', 8)).pack(side=tk.LEFT)
        tk.Entry(aoi_frame2, textvariable=self.aoi_lon_max, width=8,
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT,
                font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=(2, 0), ipady=3)

        # Date range
        tk.Label(body, text="Date Range:", bg=self.colors['bg_medium'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(anchor=tk.W)

        date_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        date_frame.pack(fill=tk.X, pady=(3, 5))

        tk.Entry(date_frame, textvariable=self.search_start_date, width=10,
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT,
                font=('Segoe UI', 8)).pack(side=tk.LEFT, ipady=3)
        tk.Label(date_frame, text="to", bg=self.colors['bg_medium'],
                fg=self.colors['text'], font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=5)
        tk.Entry(date_frame, textvariable=self.search_end_date, width=10,
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT,
                font=('Segoe UI', 8)).pack(side=tk.LEFT, ipady=3)

        # Track and direction
        param_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        param_frame.pack(fill=tk.X, pady=(0, 5))

        tk.Label(param_frame, text="Track:", bg=self.colors['bg_medium'],
                fg=self.colors['text'], font=('Segoe UI', 8)).pack(side=tk.LEFT)
        tk.Entry(param_frame, textvariable=self.track_number, width=5,
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT,
                font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=(2, 10), ipady=3)

        tk.Label(param_frame, text="Dir:", bg=self.colors['bg_medium'],
                fg=self.colors['text'], font=('Segoe UI', 8)).pack(side=tk.LEFT)
        dir_combo = ttk.Combobox(param_frame, textvariable=self.flight_direction,
                                values=["ASCENDING", "DESCENDING"], state="readonly", width=12)
        dir_combo.pack(side=tk.LEFT, padx=(2, 0))

        # Search button
        tk.Button(body, text="Search ASF", bg=self.colors['success'],
                 fg=self.colors['bg_dark'], relief=tk.FLAT, font=('Segoe UI', 9, 'bold'),
                 command=self.search_asf).pack(fill=tk.X, ipady=6, pady=(5, 5))

        # Results listbox
        tk.Label(body, text="Available Pairs:", bg=self.colors['bg_medium'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(anchor=tk.W)

        list_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        list_frame.pack(fill=tk.X, pady=(3, 5))

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.asf_listbox = tk.Listbox(list_frame, height=4, bg=self.colors['bg_light'],
                                      fg=self.colors['text'], selectbackground=self.colors['accent'],
                                      selectmode=tk.EXTENDED, relief=tk.FLAT, font=('Consolas', 7),
                                      yscrollcommand=scrollbar.set)
        self.asf_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.asf_listbox.yview)

        # Download and Process buttons
        btn_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        btn_frame.pack(fill=tk.X, pady=(5, 0))

        self.download_btn = tk.Button(btn_frame, text="Download", bg=self.colors['bg_light'],
                                      fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 8),
                                      command=self.download_selected, width=10)
        self.download_btn.pack(side=tk.LEFT, ipady=4)

        self.process_btn = tk.Button(btn_frame, text="Process ISCE2", bg=self.colors['accent'],
                                     fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 8, 'bold'),
                                     command=self.run_isce2_processing, width=12)
        self.process_btn.pack(side=tk.RIGHT, ipady=4)

        # Progress bar
        self.download_progress = ttk.Progressbar(body, style="Custom.Horizontal.TProgressbar",
                                                  mode='determinate')
        self.download_progress.pack(fill=tk.X, pady=(8, 0))

        # Conda environment
        env_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        env_frame.pack(fill=tk.X, pady=(5, 0))
        tk.Label(env_frame, text="Conda env:", bg=self.colors['bg_medium'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 8)).pack(side=tk.LEFT)
        tk.Entry(env_frame, textvariable=self.conda_env, width=10,
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT,
                font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=(5, 0), ipady=2)

    def create_analysis_card(self, parent):
        body = self.create_card(parent, "ANALYSIS TOOLS")

        tk.Label(body, text="Click Mode:", bg=self.colors['bg_medium'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(anchor=tk.W)

        mode_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        mode_frame.pack(fill=tk.X, pady=(5, 10))

        modes = [("None", "none"), ("Add Point", "point"), ("Add Region", "region")]
        for text, mode in modes:
            rb = tk.Radiobutton(mode_frame, text=text, variable=self.click_mode, value=mode,
                               bg=self.colors['bg_medium'], fg=self.colors['text'],
                               selectcolor=self.colors['bg_light'], activebackground=self.colors['bg_medium'],
                               font=('Segoe UI', 9))
            rb.pack(side=tk.LEFT, padx=(0, 10))

        # Coherence threshold
        tk.Label(body, text="Coherence Threshold:", bg=self.colors['bg_medium'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(5, 0))

        self.coh_threshold = tk.DoubleVar(value=0.3)
        coh_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        coh_frame.pack(fill=tk.X, pady=(5, 0))

        tk.Scale(coh_frame, variable=self.coh_threshold, from_=0.0, to=1.0, resolution=0.05,
                orient=tk.HORIZONTAL, bg=self.colors['bg_medium'], fg=self.colors['text'],
                highlightthickness=0, troughcolor=self.colors['bg_light']).pack(fill=tk.X)

        # Reference point
        tk.Label(body, text="Reference Point (stable area):", bg=self.colors['bg_medium'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(10, 0))

        self.ref_point_var = tk.StringVar(value="None")
        ref_combo = ttk.Combobox(body, textvariable=self.ref_point_var, state="readonly", width=25)
        ref_combo.pack(fill=tk.X, pady=(5, 0))
        self.ref_combo = ref_combo

    def create_points_card(self, parent):
        body = self.create_card(parent, "ANALYSIS POINTS")

        # Points listbox
        list_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        list_frame.pack(fill=tk.X)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.points_listbox = tk.Listbox(list_frame, height=6, bg=self.colors['bg_light'],
                                         fg=self.colors['text'], selectbackground=self.colors['accent'],
                                         relief=tk.FLAT, font=('Consolas', 8),
                                         yscrollcommand=scrollbar.set)
        self.points_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.points_listbox.yview)

        # Point buttons
        btn_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(btn_frame, text="Delete", bg=self.colors['accent'],
                 fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 8),
                 command=self.delete_selected_point, width=8).pack(side=tk.LEFT)

        tk.Button(btn_frame, text="Clear All", bg=self.colors['bg_light'],
                 fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 8),
                 command=self.clear_all_points, width=8).pack(side=tk.LEFT, padx=(5, 0))

        tk.Button(btn_frame, text="Analyze", bg=self.colors['success'],
                 fg=self.colors['bg_dark'], relief=tk.FLAT, font=('Segoe UI', 8, 'bold'),
                 command=self.analyze_points, width=8).pack(side=tk.RIGHT)

    def create_export_card(self, parent):
        body = self.create_card(parent, "EXPORT & REPORT")

        tk.Button(body, text="Export to GeoTIFF", bg=self.colors['bg_light'],
                 fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 9),
                 command=self.export_geotiff).pack(fill=tk.X, ipady=6)

        tk.Button(body, text="Export Points to CSV", bg=self.colors['bg_light'],
                 fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 9),
                 command=self.export_csv).pack(fill=tk.X, ipady=6, pady=(5, 0))

        tk.Button(body, text="Export to Shapefile", bg=self.colors['bg_light'],
                 fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 9),
                 command=self.export_shapefile).pack(fill=tk.X, ipady=6, pady=(5, 0))

        tk.Button(body, text="Generate PDF Report", bg=self.colors['accent'],
                 fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 9, 'bold'),
                 command=self.generate_report).pack(fill=tk.X, ipady=8, pady=(10, 0))

    def create_map_tab(self, parent):
        """Create the displacement map visualization tab"""
        plt.style.use('dark_background')

        self.map_fig = Figure(figsize=(10, 8), facecolor=self.colors['bg_dark'])
        self.map_ax = self.map_fig.add_subplot(111)
        self.map_ax.set_facecolor(self.colors['bg_medium'])
        self.map_ax.text(0.5, 0.5, 'Load displacement data to begin',
                        ha='center', va='center', fontsize=14, color=self.colors['text_secondary'])
        self.map_ax.set_xticks([])
        self.map_ax.set_yticks([])

        canvas_frame = tk.Frame(parent, bg=self.colors['bg_dark'])
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.map_canvas = FigureCanvasTkAgg(self.map_fig, master=canvas_frame)
        self.map_canvas.draw()
        self.map_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Connect click event
        self.map_canvas.mpl_connect('button_press_event', self.on_map_click)

        toolbar_frame = tk.Frame(parent, bg=self.colors['bg_medium'])
        toolbar_frame.pack(fill=tk.X)
        self.map_toolbar = NavigationToolbar2Tk(self.map_canvas, toolbar_frame)
        self.map_toolbar.update()

    def create_timeseries_tab(self, parent):
        """Create the time series visualization tab"""
        self.ts_fig = Figure(figsize=(10, 8), facecolor=self.colors['bg_dark'])
        self.ts_ax = self.ts_fig.add_subplot(111)
        self.ts_ax.set_facecolor(self.colors['bg_medium'])
        self.ts_ax.text(0.5, 0.5, 'Add analysis points and click "Analyze"\nto view time series',
                       ha='center', va='center', fontsize=14, color=self.colors['text_secondary'])
        self.ts_ax.set_xticks([])
        self.ts_ax.set_yticks([])

        canvas_frame = tk.Frame(parent, bg=self.colors['bg_dark'])
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.ts_canvas = FigureCanvasTkAgg(self.ts_fig, master=canvas_frame)
        self.ts_canvas.draw()
        self.ts_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar_frame = tk.Frame(parent, bg=self.colors['bg_medium'])
        toolbar_frame.pack(fill=tk.X)
        self.ts_toolbar = NavigationToolbar2Tk(self.ts_canvas, toolbar_frame)
        self.ts_toolbar.update()

    def create_stats_tab(self, parent):
        """Create the statistics tab"""
        # Stats text display
        self.stats_text = tk.Text(parent, bg=self.colors['bg_medium'],
                                  fg=self.colors['text'], relief=tk.FLAT,
                                  font=('Consolas', 10), padx=20, pady=20)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.stats_text.insert(tk.END, "Load data and analyze points to view statistics.\n\n")
        self.stats_text.insert(tk.END, "Statistics will include:\n")
        self.stats_text.insert(tk.END, "  - Mean displacement\n")
        self.stats_text.insert(tk.END, "  - Maximum subsidence/uplift\n")
        self.stats_text.insert(tk.END, "  - Displacement rate (mm/year)\n")
        self.stats_text.insert(tk.END, "  - Area affected\n")
        self.stats_text.insert(tk.END, "  - Point-by-point analysis\n")
        self.stats_text.config(state=tk.DISABLED)

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select InSAR Products Folder",
                                         initialdir="C:/Users/danes/Desktop/ice")
        if folder:
            self.folder_path.set(folder)
            self.status_var.set(f"Selected: {os.path.basename(folder)}")

    def read_geotiff(self, filepath):
        """Read GeoTIFF and return data, transform, and CRS"""
        if HAS_GDAL:
            ds = gdal.Open(filepath)
            if ds is None:
                raise Exception(f"Could not open: {filepath}")

            data = ds.ReadAsArray().astype(np.float64)
            transform = ds.GetGeoTransform()
            crs = ds.GetProjection()
            nodata = ds.GetRasterBand(1).GetNoDataValue()
            ds = None

            if nodata is not None:
                data = np.where(data == nodata, np.nan, data)

            return data, transform, crs

        elif HAS_RASTERIO:
            with rasterio.open(filepath) as src:
                data = src.read(1).astype(np.float64)
                transform = src.transform
                crs = str(src.crs) if src.crs else None
                nodata = src.nodata

                if nodata is not None:
                    data = np.where(data == nodata, np.nan, data)

                return data, transform, crs
        else:
            raise Exception("No GeoTIFF reader available")

    def parse_date_from_filename(self, filename):
        """Extract date pair from ASF InSAR filename"""
        # Pattern: S1AA_20150817T223551_20150829T223551_...
        match = re.search(r'(\d{8})T\d{6}_(\d{8})T\d{6}', filename)
        if match:
            date1 = datetime.strptime(match.group(1), '%Y%m%d')
            date2 = datetime.strptime(match.group(2), '%Y%m%d')
            return date1, date2
        return None, None

    def load_displacement_data(self):
        """Load displacement GeoTIFFs from folder"""
        folder = self.folder_path.get()
        if not folder:
            messagebox.showerror("Error", "Please select a folder first!")
            return

        try:
            self.status_var.set("Scanning for displacement files...")
            self.displacement_files = []
            self.file_listbox.delete(0, tk.END)

            # Search for displacement files (los_disp, vert_disp)
            patterns = ['*los_disp*.tif', '*vert_disp*.tif', '*displacement*.tif', '*disp*.tif']
            tif_files = []

            for pattern in patterns:
                tif_files.extend(glob.glob(os.path.join(folder, '**', pattern), recursive=True))

            # Remove duplicates
            tif_files = list(set(tif_files))

            if not tif_files:
                messagebox.showwarning("Warning", "No displacement files found!")
                return

            # Load each file
            for filepath in sorted(tif_files):
                try:
                    data, transform, crs = self.read_geotiff(filepath)
                    date1, date2 = self.parse_date_from_filename(filepath)

                    fname = os.path.basename(filepath)
                    if date1 and date2:
                        display_name = f"{date1.strftime('%Y-%m-%d')} to {date2.strftime('%Y-%m-%d')}"
                    else:
                        display_name = fname[:50]

                    self.displacement_files.append({
                        'path': filepath,
                        'name': fname,
                        'display_name': display_name,
                        'data': data,
                        'transform': transform,
                        'crs': crs,
                        'date1': date1,
                        'date2': date2
                    })

                    self.file_listbox.insert(tk.END, display_name)

                except Exception as e:
                    print(f"Error loading {filepath}: {e}")

            # Also load coherence if available
            coh_files = glob.glob(os.path.join(folder, '**', '*corr*.tif'), recursive=True)
            if coh_files:
                self.coherence_data, _, _ = self.read_geotiff(coh_files[0])

            # Load DEM if available
            dem_files = glob.glob(os.path.join(folder, '**', '*dem*.tif'), recursive=True)
            if dem_files:
                self.dem_data, _, _ = self.read_geotiff(dem_files[0])

            self.status_var.set(f"Loaded {len(self.displacement_files)} displacement files")

            # Display first file
            if self.displacement_files:
                self.display_displacement(0)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load data: {str(e)}")

    def load_hdf5_timeseries(self):
        """Load HDF5 time series file"""
        if not HAS_H5PY:
            messagebox.showerror("Error", "h5py not installed. Install with: pip install h5py")
            return

        filepath = filedialog.askopenfilename(
            title="Select HDF5 Time Series File",
            filetypes=[("HDF5 files", "*.hdf5 *.h5"), ("All files", "*.*")],
            initialdir=self.folder_path.get() or "C:/Users/danes/Desktop/ice"
        )

        if not filepath:
            return

        try:
            self.status_var.set("Loading HDF5 time series...")

            with h5py.File(filepath, 'r') as f:
                # Print structure for debugging
                def print_structure(name, obj):
                    print(name)
                f.visititems(print_structure)

                # Try common dataset names
                possible_names = ['timeseries', 'displacement', 'velocity', 'data']
                data = None

                for name in possible_names:
                    if name in f:
                        data = f[name][:]
                        break

                if data is not None:
                    messagebox.showinfo("Success",
                        f"Loaded HDF5 data with shape: {data.shape}\n"
                        f"Keys found: {list(f.keys())}")
                else:
                    messagebox.showinfo("HDF5 Structure",
                        f"Available datasets: {list(f.keys())}\n"
                        "Please check the data structure.")

            self.status_var.set("HDF5 loaded successfully")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load HDF5: {str(e)}")

    def on_file_select(self, event):
        """Handle file selection from listbox"""
        selection = self.file_listbox.curselection()
        if selection:
            self.display_displacement(selection[0])

    def display_displacement(self, index):
        """Display displacement map"""
        if index >= len(self.displacement_files):
            return

        file_info = self.displacement_files[index]
        data = file_info['data']
        self.current_data = data
        self.current_transform = file_info['transform']
        self.current_crs = file_info['crs']

        # Apply coherence mask if available
        if self.coherence_data is not None and self.coherence_data.shape == data.shape:
            threshold = self.coh_threshold.get()
            masked_data = np.where(self.coherence_data >= threshold, data, np.nan)
        else:
            masked_data = data

        # Calculate display range
        valid_data = masked_data[np.isfinite(masked_data)]
        if len(valid_data) > 0:
            vmin, vmax = np.percentile(valid_data, [2, 98])
            # Make symmetric around zero for displacement
            max_abs = max(abs(vmin), abs(vmax))
            vmin, vmax = -max_abs, max_abs
        else:
            vmin, vmax = -0.1, 0.1

        # Clear and plot
        self.map_fig.clear()
        self.map_ax = self.map_fig.add_subplot(111)
        self.map_ax.set_facecolor(self.colors['bg_medium'])

        im = self.map_ax.imshow(masked_data, cmap=self.displacement_cmap, vmin=vmin, vmax=vmax)

        # Add colorbar
        cbar = self.map_fig.colorbar(im, ax=self.map_ax, shrink=0.8)
        cbar.set_label('Displacement (m)', color=self.colors['text_secondary'])
        cbar.ax.yaxis.set_tick_params(color=self.colors['text_secondary'])
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=self.colors['text_secondary'])

        # Title
        title = f"Displacement: {file_info['display_name']}"
        self.map_ax.set_title(title, fontsize=12, color=self.colors['text'], fontweight='bold')
        self.map_ax.set_xlabel('Range (pixels)', color=self.colors['text_secondary'])
        self.map_ax.set_ylabel('Azimuth (pixels)', color=self.colors['text_secondary'])
        self.map_ax.tick_params(colors=self.colors['text_secondary'])

        # Plot existing analysis points
        self.plot_analysis_points()

        self.map_fig.tight_layout()
        self.map_canvas.draw()

        self.status_var.set(f"Displaying: {file_info['name']}")

    def plot_analysis_points(self):
        """Plot analysis points on map"""
        for i, (x, y, name) in enumerate(self.analysis_points):
            self.map_ax.plot(x, y, 'o', markersize=10, markerfacecolor='yellow',
                            markeredgecolor='black', markeredgewidth=2)
            self.map_ax.annotate(name, (x, y), xytext=(5, 5), textcoords='offset points',
                                fontsize=9, color='yellow', fontweight='bold')

        for x1, y1, x2, y2, name in self.analysis_regions:
            rect = Rectangle((x1, y1), x2-x1, y2-y1, fill=False,
                             edgecolor='yellow', linewidth=2)
            self.map_ax.add_patch(rect)
            self.map_ax.annotate(name, (x1, y1), xytext=(5, -15), textcoords='offset points',
                                fontsize=9, color='yellow', fontweight='bold')

    def on_map_click(self, event):
        """Handle click on map"""
        if event.inaxes != self.map_ax or self.current_data is None:
            return

        x, y = int(event.xdata), int(event.ydata)

        if self.click_mode.get() == "point":
            # Add new point
            name = f"P{len(self.analysis_points) + 1}"
            self.analysis_points.append((x, y, name))
            self.points_listbox.insert(tk.END, f"{name}: ({x}, {y})")

            # Update reference point combo
            self.update_ref_combo()

            # Redraw
            self.display_displacement(self.file_listbox.curselection()[0] if self.file_listbox.curselection() else 0)

            self.status_var.set(f"Added point {name} at ({x}, {y})")

        elif self.click_mode.get() == "region":
            if self.region_start is None:
                self.region_start = (x, y)
                self.status_var.set(f"Region start: ({x}, {y}). Click again for end point.")
            else:
                x1, y1 = self.region_start
                name = f"R{len(self.analysis_regions) + 1}"
                self.analysis_regions.append((min(x1, x), min(y1, y), max(x1, x), max(y1, y), name))
                self.points_listbox.insert(tk.END, f"{name}: ({x1},{y1}) to ({x},{y})")
                self.region_start = None

                # Redraw
                self.display_displacement(self.file_listbox.curselection()[0] if self.file_listbox.curselection() else 0)

                self.status_var.set(f"Added region {name}")

    def update_ref_combo(self):
        """Update reference point combobox"""
        points = ["None"] + [p[2] for p in self.analysis_points]
        self.ref_combo['values'] = points

    def delete_selected_point(self):
        """Delete selected point/region"""
        selection = self.points_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        item_text = self.points_listbox.get(idx)

        # Determine if point or region
        if item_text.startswith('P'):
            # Find and remove point
            for i, (x, y, name) in enumerate(self.analysis_points):
                if name == item_text.split(':')[0]:
                    self.analysis_points.pop(i)
                    break
        else:
            # Find and remove region
            for i, (*_, name) in enumerate(self.analysis_regions):
                if name == item_text.split(':')[0]:
                    self.analysis_regions.pop(i)
                    break

        self.points_listbox.delete(idx)
        self.update_ref_combo()

        # Redraw
        if self.displacement_files:
            self.display_displacement(self.file_listbox.curselection()[0] if self.file_listbox.curselection() else 0)

    def clear_all_points(self):
        """Clear all analysis points and regions"""
        self.analysis_points = []
        self.analysis_regions = []
        self.points_listbox.delete(0, tk.END)
        self.update_ref_combo()

        if self.displacement_files:
            self.display_displacement(self.file_listbox.curselection()[0] if self.file_listbox.curselection() else 0)

    def analyze_points(self):
        """Analyze displacement at selected points"""
        if not self.analysis_points and not self.analysis_regions:
            messagebox.showwarning("Warning", "Add at least one analysis point or region!")
            return

        if not self.displacement_files:
            messagebox.showwarning("Warning", "Load displacement data first!")
            return

        self.status_var.set("Analyzing points...")

        # Get reference point displacement if set
        ref_disp = 0
        ref_name = self.ref_point_var.get()
        if ref_name != "None":
            for x, y, name in self.analysis_points:
                if name == ref_name:
                    ref_disp = self.current_data[y, x] if np.isfinite(self.current_data[y, x]) else 0
                    break

        # Collect time series data
        self.time_series_data = {}

        for x, y, name in self.analysis_points:
            self.time_series_data[name] = []

            for file_info in self.displacement_files:
                data = file_info['data']
                if 0 <= y < data.shape[0] and 0 <= x < data.shape[1]:
                    disp = data[y, x]
                    if np.isfinite(disp):
                        disp -= ref_disp  # Apply reference correction
                        date = file_info['date2'] or datetime.now()
                        self.time_series_data[name].append((date, disp))

        # Plot time series
        self.plot_time_series()

        # Update statistics
        self.update_statistics()

        self.status_var.set("Analysis complete")

    def plot_time_series(self):
        """Plot time series for all points"""
        self.ts_fig.clear()
        self.ts_ax = self.ts_fig.add_subplot(111)
        self.ts_ax.set_facecolor(self.colors['bg_medium'])

        colors_list = plt.cm.tab10.colors

        for i, (name, data) in enumerate(self.time_series_data.items()):
            if data:
                dates = [d[0] for d in data]
                disps = [d[1] * 1000 for d in data]  # Convert to mm

                color = colors_list[i % len(colors_list)]
                self.ts_ax.plot(dates, disps, 'o-', label=name, color=color,
                               markersize=8, linewidth=2)

        self.ts_ax.axhline(y=0, color='white', linestyle='--', alpha=0.5)

        self.ts_ax.set_title('Displacement Time Series', fontsize=14,
                            color=self.colors['text'], fontweight='bold')
        self.ts_ax.set_xlabel('Date', color=self.colors['text_secondary'])
        self.ts_ax.set_ylabel('Displacement (mm)', color=self.colors['text_secondary'])
        self.ts_ax.tick_params(colors=self.colors['text_secondary'])
        self.ts_ax.legend(loc='best', facecolor=self.colors['bg_light'],
                         edgecolor=self.colors['border'])

        # Annotations
        self.ts_ax.text(0.02, 0.98, 'Negative = Subsidence\nPositive = Uplift',
                       transform=self.ts_ax.transAxes, fontsize=9,
                       color=self.colors['text_secondary'], va='top')

        self.ts_fig.autofmt_xdate()
        self.ts_fig.tight_layout()
        self.ts_canvas.draw()

        # Switch to time series tab
        self.notebook.select(1)

    def update_statistics(self):
        """Update statistics display"""
        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete(1.0, tk.END)

        self.stats_text.insert(tk.END, "=" * 60 + "\n")
        self.stats_text.insert(tk.END, "     LAND SUBSIDENCE ANALYSIS REPORT\n")
        self.stats_text.insert(tk.END, "=" * 60 + "\n\n")

        self.stats_text.insert(tk.END, f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        self.stats_text.insert(tk.END, f"Number of Files: {len(self.displacement_files)}\n")
        self.stats_text.insert(tk.END, f"Analysis Points: {len(self.analysis_points)}\n")
        self.stats_text.insert(tk.END, f"Analysis Regions: {len(self.analysis_regions)}\n\n")

        # Overall statistics
        if self.current_data is not None:
            valid = self.current_data[np.isfinite(self.current_data)]
            if len(valid) > 0:
                self.stats_text.insert(tk.END, "-" * 40 + "\n")
                self.stats_text.insert(tk.END, "OVERALL DISPLACEMENT STATISTICS\n")
                self.stats_text.insert(tk.END, "-" * 40 + "\n")
                self.stats_text.insert(tk.END, f"  Mean:    {np.mean(valid)*1000:>10.2f} mm\n")
                self.stats_text.insert(tk.END, f"  Median:  {np.median(valid)*1000:>10.2f} mm\n")
                self.stats_text.insert(tk.END, f"  Std Dev: {np.std(valid)*1000:>10.2f} mm\n")
                self.stats_text.insert(tk.END, f"  Min:     {np.min(valid)*1000:>10.2f} mm\n")
                self.stats_text.insert(tk.END, f"  Max:     {np.max(valid)*1000:>10.2f} mm\n\n")

                # Subsidence area
                subsidence_pixels = np.sum(valid < -0.01)  # > 10mm subsidence
                total_pixels = len(valid)
                self.stats_text.insert(tk.END, f"  Pixels with >10mm subsidence: {subsidence_pixels} ({100*subsidence_pixels/total_pixels:.1f}%)\n\n")

        # Point statistics
        self.stats_text.insert(tk.END, "-" * 40 + "\n")
        self.stats_text.insert(tk.END, "POINT-BY-POINT ANALYSIS\n")
        self.stats_text.insert(tk.END, "-" * 40 + "\n\n")

        for name, data in self.time_series_data.items():
            if data:
                disps = [d[1] * 1000 for d in data]
                self.stats_text.insert(tk.END, f"  {name}:\n")
                self.stats_text.insert(tk.END, f"    Displacement: {disps[-1]:.2f} mm\n")

                if len(data) >= 2:
                    # Calculate rate
                    dates = [d[0] for d in data]
                    days = (dates[-1] - dates[0]).days
                    if days > 0:
                        rate = (disps[-1] - disps[0]) / (days / 365.25)
                        self.stats_text.insert(tk.END, f"    Rate: {rate:.2f} mm/year\n")

                self.stats_text.insert(tk.END, "\n")

        self.stats_text.config(state=tk.DISABLED)

    def export_geotiff(self):
        """Export current displacement to GeoTIFF"""
        if self.current_data is None:
            messagebox.showerror("Error", "No data to export!")
            return

        save_path = filedialog.asksaveasfilename(
            title="Save GeoTIFF",
            defaultextension=".tif",
            filetypes=[("GeoTIFF", "*.tif"), ("All files", "*.*")]
        )

        if not save_path:
            return

        try:
            if HAS_GDAL:
                driver = gdal.GetDriverByName('GTiff')
                rows, cols = self.current_data.shape
                ds = driver.Create(save_path, cols, rows, 1, gdal.GDT_Float32)

                if self.current_transform:
                    ds.SetGeoTransform(self.current_transform)
                if self.current_crs:
                    ds.SetProjection(self.current_crs)

                ds.GetRasterBand(1).WriteArray(self.current_data)
                ds.GetRasterBand(1).SetNoDataValue(np.nan)
                ds = None

                messagebox.showinfo("Success", f"GeoTIFF saved to:\n{save_path}")
            else:
                messagebox.showerror("Error", "GDAL required for GeoTIFF export")

        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def export_csv(self):
        """Export point data to CSV"""
        if not self.time_series_data:
            messagebox.showerror("Error", "No analysis data! Run analysis first.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Save CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not save_path:
            return

        try:
            with open(save_path, 'w') as f:
                f.write("Point,X,Y,Date,Displacement_m,Displacement_mm\n")

                for name, data in self.time_series_data.items():
                    # Find coordinates
                    x, y = 0, 0
                    for px, py, pname in self.analysis_points:
                        if pname == name:
                            x, y = px, py
                            break

                    for date, disp in data:
                        f.write(f"{name},{x},{y},{date.strftime('%Y-%m-%d')},{disp:.6f},{disp*1000:.3f}\n")

            messagebox.showinfo("Success", f"CSV saved to:\n{save_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def export_shapefile(self):
        """Export points to shapefile"""
        if not HAS_GDAL:
            messagebox.showerror("Error", "GDAL required for shapefile export")
            return

        if not self.analysis_points:
            messagebox.showerror("Error", "No analysis points to export!")
            return

        save_path = filedialog.asksaveasfilename(
            title="Save Shapefile",
            defaultextension=".shp",
            filetypes=[("Shapefile", "*.shp"), ("All files", "*.*")]
        )

        if not save_path:
            return

        try:
            driver = ogr.GetDriverByName('ESRI Shapefile')
            ds = driver.CreateDataSource(save_path)

            # Create spatial reference
            srs = osr.SpatialReference()
            if self.current_crs:
                srs.ImportFromWkt(self.current_crs)
            else:
                srs.ImportFromEPSG(4326)

            layer = ds.CreateLayer('points', srs, ogr.wkbPoint)

            # Add fields
            layer.CreateField(ogr.FieldDefn('Name', ogr.OFTString))
            layer.CreateField(ogr.FieldDefn('Disp_mm', ogr.OFTReal))
            layer.CreateField(ogr.FieldDefn('X_pixel', ogr.OFTInteger))
            layer.CreateField(ogr.FieldDefn('Y_pixel', ogr.OFTInteger))

            for x, y, name in self.analysis_points:
                # Get displacement value
                disp = 0
                if name in self.time_series_data and self.time_series_data[name]:
                    disp = self.time_series_data[name][-1][1] * 1000

                # Convert pixel to geo coordinates if transform available
                if self.current_transform:
                    geo_x = self.current_transform[0] + x * self.current_transform[1]
                    geo_y = self.current_transform[3] + y * self.current_transform[5]
                else:
                    geo_x, geo_y = x, y

                feature = ogr.Feature(layer.GetLayerDefn())
                feature.SetField('Name', name)
                feature.SetField('Disp_mm', disp)
                feature.SetField('X_pixel', x)
                feature.SetField('Y_pixel', y)

                point = ogr.Geometry(ogr.wkbPoint)
                point.AddPoint(geo_x, geo_y)
                feature.SetGeometry(point)

                layer.CreateFeature(feature)
                feature = None

            ds = None
            messagebox.showinfo("Success", f"Shapefile saved to:\n{save_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def generate_report(self):
        """Generate PDF report"""
        if not HAS_REPORTLAB:
            messagebox.showerror("Error", "reportlab not installed.\nInstall with: pip install reportlab")
            return

        save_path = filedialog.asksaveasfilename(
            title="Save PDF Report",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )

        if not save_path:
            return

        try:
            self.status_var.set("Generating PDF report...")

            doc = SimpleDocTemplate(save_path, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                alignment=1  # Center
            )
            story.append(Paragraph("Land Subsidence Analysis Report", title_style))
            story.append(Spacer(1, 20))

            # Info
            story.append(Paragraph(f"<b>Report Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
            story.append(Paragraph(f"<b>Data Files:</b> {len(self.displacement_files)}", styles['Normal']))
            story.append(Paragraph(f"<b>Analysis Points:</b> {len(self.analysis_points)}", styles['Normal']))
            story.append(Spacer(1, 20))

            # Save figures temporarily
            import tempfile

            # Displacement map
            map_path = os.path.join(tempfile.gettempdir(), 'disp_map.png')
            self.map_fig.savefig(map_path, dpi=150, bbox_inches='tight', facecolor='white')
            story.append(Paragraph("<b>Displacement Map</b>", styles['Heading2']))
            story.append(Image(map_path, width=6*inch, height=4.5*inch))
            story.append(Spacer(1, 20))

            # Time series
            if self.time_series_data:
                ts_path = os.path.join(tempfile.gettempdir(), 'time_series.png')
                self.ts_fig.savefig(ts_path, dpi=150, bbox_inches='tight', facecolor='white')
                story.append(Paragraph("<b>Displacement Time Series</b>", styles['Heading2']))
                story.append(Image(ts_path, width=6*inch, height=4*inch))
                story.append(Spacer(1, 20))

            # Statistics table
            story.append(Paragraph("<b>Point Statistics</b>", styles['Heading2']))

            table_data = [['Point', 'X', 'Y', 'Displacement (mm)']]
            for name, data in self.time_series_data.items():
                x, y = 0, 0
                for px, py, pname in self.analysis_points:
                    if pname == name:
                        x, y = px, py
                        break

                disp = data[-1][1] * 1000 if data else 0
                table_data.append([name, str(x), str(y), f"{disp:.2f}"])

            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)

            # Build PDF
            doc.build(story)

            # Cleanup temp files
            try:
                os.remove(map_path)
                if self.time_series_data:
                    os.remove(ts_path)
            except:
                pass

            messagebox.showinfo("Success", f"PDF report saved to:\n{save_path}")
            self.status_var.set("Report generated successfully")

        except Exception as e:
            messagebox.showerror("Error", f"Report generation failed: {str(e)}")

    # ==================== ASF DOWNLOAD & ISCE2 PROCESSING ====================

    def search_asf(self):
        """Search ASF for Sentinel-1 SLC data"""
        if not HAS_ASF:
            messagebox.showerror("Error", "asf_search not installed")
            return

        # Validate inputs
        try:
            lat_min = float(self.aoi_lat_min.get())
            lat_max = float(self.aoi_lat_max.get())
            lon_min = float(self.aoi_lon_min.get())
            lon_max = float(self.aoi_lon_max.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid coordinates. Enter numeric lat/lon values.")
            return

        try:
            start = datetime.strptime(self.search_start_date.get(), '%Y-%m-%d')
            end = datetime.strptime(self.search_end_date.get(), '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
            return

        self.status_var.set("Searching ASF archive...")
        self.asf_listbox.delete(0, tk.END)

        # Create WKT polygon
        wkt = f"POLYGON(({lon_min} {lat_min},{lon_max} {lat_min},{lon_max} {lat_max},{lon_min} {lat_max},{lon_min} {lat_min}))"

        try:
            # Build search parameters
            search_params = {
                'platform': [asf.PLATFORM.SENTINEL1],
                'processingLevel': [asf.PRODUCT_TYPE.SLC],
                'beamMode': asf.BEAMMODE.IW,
                'intersectsWith': wkt,
                'start': start,
                'end': end,
                'flightDirection': self.flight_direction.get(),
            }

            # Add track number if specified
            track = self.track_number.get().strip()
            if track:
                try:
                    search_params['relativeOrbit'] = int(track)
                except ValueError:
                    pass

            # Execute search
            results = asf.search(**search_params)
            self.asf_search_results = list(results)

            if not self.asf_search_results:
                messagebox.showinfo("Search Results", "No Sentinel-1 SLC data found for the specified criteria.")
                self.status_var.set("No data found")
                return

            # Sort by date
            self.asf_search_results.sort(key=lambda x: x.properties.get('startTime', ''))

            # Display results
            for i, result in enumerate(self.asf_search_results):
                props = result.properties
                start_time = props.get('startTime', '')[:10]
                track_num = props.get('pathNumber', 'N/A')
                self.asf_listbox.insert(tk.END, f"{start_time} | Track {track_num}")

            self.status_var.set(f"Found {len(self.asf_search_results)} scenes")

        except Exception as e:
            messagebox.showerror("Search Error", f"ASF search failed:\n{str(e)}")
            self.status_var.set("Search failed")

    def download_selected(self):
        """Download selected SLC scenes from ASF"""
        if not HAS_ASF:
            return

        selection = self.asf_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select at least one scene to download")
            return

        if len(selection) < 2:
            messagebox.showwarning("Warning", "Select at least 2 scenes for InSAR processing")
            return

        # Validate credentials
        user = self.earthdata_user.get().strip()
        password = self.earthdata_pass.get().strip()

        if not user or not password:
            messagebox.showerror("Error", "Enter NASA Earthdata credentials")
            return

        self.selected_pair_indices = list(selection)

        # Start download in background thread
        if self.is_downloading:
            messagebox.showwarning("Warning", "Download already in progress")
            return

        self.download_thread = threading.Thread(target=self._download_worker, daemon=True)
        self.download_thread.start()

    def _download_worker(self):
        """Background worker for downloading SLC data"""
        self.is_downloading = True
        self.root.after(0, lambda: self.download_btn.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.status_var.set("Starting download..."))

        try:
            # Create session
            session = asf.ASFSession()
            session.auth_with_creds(self.earthdata_user.get(), self.earthdata_pass.get())

            # Create download directory
            download_base = self.download_dir.get()
            os.makedirs(download_base, exist_ok=True)
            slc_dir = os.path.join(download_base, "SLC")
            os.makedirs(slc_dir, exist_ok=True)

            # Download selected scenes
            scenes_to_download = [self.asf_search_results[i] for i in self.selected_pair_indices]
            total = len(scenes_to_download)

            for i, scene in enumerate(scenes_to_download):
                progress = int((i / total) * 100)
                self.root.after(0, lambda p=progress: self.download_progress.config(value=p))
                self.root.after(0, lambda n=scene.properties.get('fileID', 'unknown'):
                              self.status_var.set(f"Downloading: {n[:40]}..."))

                scene.download(path=slc_dir, session=session)

            self.root.after(0, lambda: self.download_progress.config(value=100))
            self.root.after(0, lambda: self.status_var.set(f"Downloaded {total} scenes to {slc_dir}"))
            self.root.after(0, lambda: messagebox.showinfo("Success",
                f"Downloaded {total} SLC scenes to:\n{slc_dir}"))

        except Exception as e:
            self.root.after(0, lambda err=str(e): messagebox.showerror("Download Error", f"Download failed:\n{err}"))
            self.root.after(0, lambda: self.status_var.set("Download failed"))

        finally:
            self.is_downloading = False
            self.root.after(0, lambda: self.download_btn.config(state=tk.NORMAL))

    def run_isce2_processing(self):
        """Run ISCE2 topsApp.py processing"""
        if self.is_processing:
            messagebox.showwarning("Warning", "Processing already in progress")
            return

        # Check for downloaded SLC files
        download_base = self.download_dir.get()
        slc_dir = os.path.join(download_base, "SLC")

        if not os.path.exists(slc_dir):
            messagebox.showerror("Error", f"SLC directory not found:\n{slc_dir}\n\nDownload data first.")
            return

        # Find SAFE files
        safe_files = glob.glob(os.path.join(slc_dir, "*.zip")) + glob.glob(os.path.join(slc_dir, "*.SAFE"))

        if len(safe_files) < 2:
            messagebox.showerror("Error", "Need at least 2 SLC files for InSAR processing")
            return

        # Sort by date (filename contains date)
        safe_files.sort()

        # Use first as reference, second as secondary
        reference_safe = safe_files[0]
        secondary_safe = safe_files[1]

        # Create processing directory
        proc_dir = os.path.join(download_base, "processing")
        os.makedirs(proc_dir, exist_ok=True)

        # Generate config files
        try:
            self._generate_isce2_config(reference_safe, secondary_safe, proc_dir)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate config:\n{str(e)}")
            return

        # Start processing in background
        self.processing_thread = threading.Thread(
            target=self._isce2_worker,
            args=(proc_dir,),
            daemon=True
        )
        self.processing_thread.start()

    def _generate_isce2_config(self, ref_safe, sec_safe, proc_dir):
        """Generate ISCE2 topsApp.xml configuration"""
        # Get AOI for geocoding
        try:
            lat_min = float(self.aoi_lat_min.get())
            lat_max = float(self.aoi_lat_max.get())
            lon_min = float(self.aoi_lon_min.get())
            lon_max = float(self.aoi_lon_max.get())
            geocode_bbox = f"[{lat_min}, {lat_max}, {lon_min}, {lon_max}]"
        except:
            geocode_bbox = None

        # Use forward slashes for ISCE2 (even on Windows)
        ref_safe = ref_safe.replace('\\', '/')
        sec_safe = sec_safe.replace('\\', '/')

        # Main topsApp.xml
        topsapp_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<topsApp>
    <component name="topsinsar">
        <property name="Sensor name">SENTINEL1</property>

        <component name="reference">
            <property name="safe">{ref_safe}</property>
            <property name="output directory">reference</property>
        </component>

        <component name="secondary">
            <property name="safe">{sec_safe}</property>
            <property name="output directory">secondary</property>
        </component>

        <property name="do unwrap">True</property>
        <property name="unwrapper name">snaphu_mcf</property>

        <property name="do ESD">True</property>

        <property name="range looks">7</property>
        <property name="azimuth looks">2</property>
        <property name="filter strength">0.5</property>

        {f'<property name="geocode bounding box">{geocode_bbox}</property>' if geocode_bbox else ''}

    </component>
</topsApp>
'''
        # Write config file
        config_path = os.path.join(proc_dir, "topsApp.xml")
        with open(config_path, 'w') as f:
            f.write(topsapp_xml)

        self.status_var.set(f"Config written to {config_path}")

    def _isce2_worker(self, proc_dir):
        """Background worker for ISCE2 processing"""
        self.is_processing = True
        self.root.after(0, lambda: self.process_btn.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.status_var.set("Starting ISCE2 processing..."))
        self.root.after(0, lambda: self.download_progress.config(mode='indeterminate'))
        self.root.after(0, lambda: self.download_progress.start(10))

        try:
            conda_env = self.conda_env.get().strip() or "isce2"

            # Build command
            cmd = f'conda run -n {conda_env} topsApp.py topsApp.xml'

            self.root.after(0, lambda: self.status_var.set(f"Running: {cmd}"))

            # Run ISCE2
            process = subprocess.Popen(
                cmd,
                shell=True,
                cwd=proc_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            # Monitor output
            for line in process.stdout:
                line = line.strip()
                if line:
                    # Update status with current step
                    if 'runPreprocessor' in line:
                        self.root.after(0, lambda: self.status_var.set("ISCE2: Preprocessing..."))
                    elif 'runTopo' in line:
                        self.root.after(0, lambda: self.status_var.set("ISCE2: Computing topography..."))
                    elif 'runBurstIfg' in line:
                        self.root.after(0, lambda: self.status_var.set("ISCE2: Creating interferograms..."))
                    elif 'runMergeBursts' in line:
                        self.root.after(0, lambda: self.status_var.set("ISCE2: Merging bursts..."))
                    elif 'runFilter' in line:
                        self.root.after(0, lambda: self.status_var.set("ISCE2: Filtering..."))
                    elif 'runUnwrap' in line:
                        self.root.after(0, lambda: self.status_var.set("ISCE2: Unwrapping phase..."))
                    elif 'runGeocode' in line:
                        self.root.after(0, lambda: self.status_var.set("ISCE2: Geocoding..."))

            process.wait()

            if process.returncode == 0:
                self.root.after(0, lambda: self.status_var.set("ISCE2 processing complete!"))
                self.root.after(0, lambda: messagebox.showinfo("Success",
                    f"ISCE2 processing complete!\n\nResults in:\n{os.path.join(proc_dir, 'merged')}"))

                # Auto-load results
                merged_dir = os.path.join(proc_dir, "merged")
                if os.path.exists(merged_dir):
                    self.root.after(0, lambda: self._load_isce2_results(merged_dir))
            else:
                self.root.after(0, lambda: messagebox.showerror("Error",
                    f"ISCE2 processing failed with return code {process.returncode}"))
                self.root.after(0, lambda: self.status_var.set("ISCE2 processing failed"))

        except Exception as e:
            self.root.after(0, lambda err=str(e): messagebox.showerror("Error", f"ISCE2 failed:\n{err}"))
            self.root.after(0, lambda: self.status_var.set("ISCE2 processing failed"))

        finally:
            self.is_processing = False
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.download_progress.stop())
            self.root.after(0, lambda: self.download_progress.config(mode='determinate', value=0))

    def _load_isce2_results(self, merged_dir):
        """Load ISCE2 output files into the analyzer"""
        self.folder_path.set(merged_dir)
        self.status_var.set(f"Loading results from {merged_dir}...")

        # Look for displacement/phase files
        self.load_displacement_data()


if __name__ == "__main__":
    root = tk.Tk()
    app = LandSubsidenceAnalyzer(root)
    root.mainloop()
