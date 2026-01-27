"""
ASF InSAR Product Viewer - Standalone Edition
==============================================
Professional viewer for ASF On-Demand InSAR GeoTIFF products.
Optimized for PyInstaller executable creation.

Version: 1.0
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import os
import glob
import sys

# Handle matplotlib backend for exe
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap

# Try imports with fallbacks
HAS_RASTERIO = False
HAS_GDAL = False

try:
    import rasterio
    HAS_RASTERIO = True
except ImportError:
    pass

if not HAS_RASTERIO:
    try:
        from osgeo import gdal
        gdal.UseExceptions()
        HAS_GDAL = True
    except ImportError:
        pass


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class ASFInSARViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("ASF InSAR Product Viewer v1.0")
        self.root.geometry("1600x950")
        self.root.minsize(1300, 850)
        
        # Set icon if available
        try:
            self.root.iconbitmap(resource_path('icon.ico'))
        except:
            pass
        
        # Color scheme - Professional dark theme
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
            'border': '#2d3748'
        }
        
        self.root.configure(bg=self.colors['bg_dark'])
        
        # Variables
        self.folder_path = tk.StringVar()
        self.status_var = tk.StringVar(value="Welcome! Select a folder containing InSAR GeoTIFF products.")
        self.colormap_var = tk.StringVar(value="auto")
        self.vmin_var = tk.StringVar(value="auto")
        self.vmax_var = tk.StringVar(value="auto")
        
        # Data storage
        self.tif_files = []
        self.current_data = None
        self.current_file = None
        self.geo_transform = None
        self.projection = None
        
        # Custom colormaps
        self.custom_cmaps = self.create_insar_colormaps()
        
        # Product type detection patterns
        self.product_patterns = {
            'wrapped_phase': ['wrapped_phase', 'phase_wrapped', 'wrapped'],
            'unwrapped_phase': ['unwrapped_phase', 'phase_unwrapped', 'unwrapped', 'unw'],
            'coherence': ['corr', 'coherence', 'coh'],
            'amplitude': ['amp', 'amplitude'],
            'dem': ['dem', 'elevation', 'height'],
            'displacement': ['displacement', 'disp', 'los'],
            'vertical_disp': ['vert', 'vertical'],
            'incidence': ['inc', 'incidence', 'lv_theta'],
            'azimuth': ['lv_phi', 'azimuth']
        }
        
        self.setup_styles()
        self.create_widgets()
        
        # Check for required libraries
        if not HAS_GDAL and not HAS_RASTERIO:
            messagebox.showerror("Missing Libraries", 
                "GeoTIFF reader not found!\n\n"
                "Please install rasterio:\n"
                "  pip install rasterio\n\n"
                "The application will not work without this library.")
    
    def create_insar_colormaps(self):
        """Create custom colormaps for InSAR products"""
        custom_cmaps = {}
        
        # Wrapped phase - cyclic rainbow
        phase_colors = ['#ff0000', '#ffff00', '#00ff00', '#00ffff', '#0000ff', '#ff00ff', '#ff0000']
        custom_cmaps['phase'] = LinearSegmentedColormap.from_list('phase', phase_colors, N=256)
        
        # Coherence - black to white through accent
        coh_colors = ['#000000', '#1a1a2e', '#16213e', '#0f3460', '#e94560', '#ff6b6b', '#ffffff']
        custom_cmaps['coherence'] = LinearSegmentedColormap.from_list('coherence', coh_colors, N=256)
        
        # Displacement - blue-white-red
        disp_colors = ['#0000ff', '#4444ff', '#8888ff', '#ffffff', '#ff8888', '#ff4444', '#ff0000']
        custom_cmaps['displacement'] = LinearSegmentedColormap.from_list('displacement', disp_colors, N=256)
        
        # DEM - terrain colors
        dem_colors = ['#006400', '#228B22', '#90EE90', '#FFFF00', '#FFA500', '#8B4513', '#FFFFFF']
        custom_cmaps['terrain'] = LinearSegmentedColormap.from_list('terrain_custom', dem_colors, N=256)
        
        return custom_cmaps
    
    def get_colormap(self, name):
        """Get colormap by name"""
        if name in self.custom_cmaps:
            return self.custom_cmaps[name]
        try:
            return plt.get_cmap(name)
        except:
            return plt.get_cmap('viridis')
    
    def detect_product_type(self, filename):
        """Detect InSAR product type from filename"""
        fname_lower = filename.lower()
        for product_type, patterns in self.product_patterns.items():
            for pattern in patterns:
                if pattern in fname_lower:
                    return product_type
        return 'unknown'
    
    def get_default_colormap(self, product_type):
        """Get appropriate colormap for product type"""
        cmap_mapping = {
            'wrapped_phase': 'phase',
            'unwrapped_phase': 'phase',
            'coherence': 'gray',
            'amplitude': 'gray',
            'dem': 'terrain',
            'displacement': 'displacement',
            'vertical_disp': 'displacement',
            'incidence': 'viridis',
            'azimuth': 'hsv',
            'unknown': 'viridis'
        }
        return cmap_mapping.get(product_type, 'viridis')
    
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Dark.TFrame', background=self.colors['bg_dark'])
        style.configure('Title.TLabel', background=self.colors['bg_dark'],
                       foreground=self.colors['text'], font=('Segoe UI', 24, 'bold'))
        style.configure('Subtitle.TLabel', background=self.colors['bg_dark'],
                       foreground=self.colors['text_secondary'], font=('Segoe UI', 10))
        style.configure('Status.TLabel', background=self.colors['bg_light'],
                       foreground=self.colors['text'], font=('Segoe UI', 9), padding=10)
        style.configure("Custom.Horizontal.TProgressbar",
                       background=self.colors['accent'], troughcolor=self.colors['bg_light'])
    
    def create_widgets(self):
        main_container = ttk.Frame(self.root, style='Dark.TFrame')
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Header
        header_frame = ttk.Frame(main_container, style='Dark.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(header_frame, text="ASF InSAR Product Viewer", style='Title.TLabel').pack(side=tk.LEFT)
        ttk.Label(header_frame, text="GeoTIFF Visualization Tool", 
                 style='Subtitle.TLabel').pack(side=tk.LEFT, padx=(20, 0), pady=(10, 0))
        
        # Left Panel
        left_panel = ttk.Frame(main_container, style='Dark.TFrame', width=400)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        left_panel.pack_propagate(False)
        
        self.create_folder_card(left_panel)
        self.create_products_card(left_panel)
        self.create_options_card(left_panel)
        self.create_actions_card(left_panel)
        self.create_info_card(left_panel)
        
        # Right Panel
        right_panel = ttk.Frame(main_container, style='Dark.TFrame')
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.create_visualization_panel(right_panel)
        
        # Status Bar
        status_frame = ttk.Frame(self.root, style='Dark.TFrame')
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(status_frame, textvariable=self.status_var, style='Status.TLabel').pack(fill=tk.X)
    
    def create_card(self, parent, title):
        card = tk.Frame(parent, bg=self.colors['bg_medium'], 
                       highlightbackground=self.colors['border'], highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 15))
        
        header = tk.Frame(card, bg=self.colors['bg_light'], height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=title, bg=self.colors['bg_light'], 
                fg=self.colors['text'], font=('Segoe UI', 11, 'bold')).pack(side=tk.LEFT, padx=15, pady=8)
        
        body = tk.Frame(card, bg=self.colors['bg_medium'])
        body.pack(fill=tk.X, padx=15, pady=15)
        return body
    
    def create_folder_card(self, parent):
        body = self.create_card(parent, "FOLDER SELECTION")
        
        tk.Label(body, text="Select folder with GeoTIFF files:", 
                bg=self.colors['bg_medium'], fg=self.colors['text_secondary'], 
                font=('Segoe UI', 9)).pack(anchor=tk.W)
        
        file_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        file_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.folder_entry = tk.Entry(file_frame, textvariable=self.folder_path, 
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT, 
                font=('Segoe UI', 9))
        self.folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 10))
        
        tk.Button(file_frame, text="Browse", bg=self.colors['accent'], 
                 fg=self.colors['text'], activebackground=self.colors['accent_hover'],
                 relief=tk.FLAT, font=('Segoe UI', 9, 'bold'), cursor='hand2',
                 command=self.browse_folder).pack(side=tk.RIGHT, ipadx=15, ipady=5)
    
    def create_products_card(self, parent):
        body = self.create_card(parent, "AVAILABLE PRODUCTS")
        
        list_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.product_listbox = tk.Listbox(list_frame, height=10,
                                          bg=self.colors['bg_light'], 
                                          fg=self.colors['text'],
                                          selectbackground=self.colors['accent'],
                                          selectforeground=self.colors['text'],
                                          relief=tk.FLAT, font=('Consolas', 9),
                                          yscrollcommand=scrollbar.set)
        self.product_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.product_listbox.bind('<<ListboxSelect>>', self.on_product_select)
        scrollbar.config(command=self.product_listbox.yview)
    
    def create_options_card(self, parent):
        body = self.create_card(parent, "DISPLAY OPTIONS")
        
        options_grid = tk.Frame(body, bg=self.colors['bg_medium'])
        options_grid.pack(fill=tk.X)
        
        # Colormap
        tk.Label(options_grid, text="Colormap:", bg=self.colors['bg_medium'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).grid(row=0, column=0, sticky=tk.W, pady=5)
        
        colormaps = ["auto", "phase", "coherence", "displacement", "terrain", 
                     "jet", "viridis", "plasma", "inferno", "magma", 
                     "gray", "RdBu_r", "seismic", "hsv"]
        cmap_combo = ttk.Combobox(options_grid, textvariable=self.colormap_var, 
                                  values=colormaps, width=15, state="readonly")
        cmap_combo.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        cmap_combo.bind('<<ComboboxSelected>>', self.on_colormap_change)
        
        # Min/Max
        tk.Label(options_grid, text="Min Value:", bg=self.colors['bg_medium'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).grid(row=1, column=0, sticky=tk.W, pady=5)
        tk.Entry(options_grid, textvariable=self.vmin_var, width=12,
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        tk.Label(options_grid, text="Max Value:", bg=self.colors['bg_medium'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).grid(row=2, column=0, sticky=tk.W, pady=5)
        tk.Entry(options_grid, textvariable=self.vmax_var, width=12,
                bg=self.colors['bg_light'], fg=self.colors['text'],
                insertbackground=self.colors['text'], relief=tk.FLAT).grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        tk.Button(options_grid, text="Apply", bg=self.colors['bg_light'],
                 fg=self.colors['text'], activebackground=self.colors['border'],
                 relief=tk.FLAT, font=('Segoe UI', 9), cursor='hand2', width=10,
                 command=self.apply_settings).grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=10)
    
    def create_actions_card(self, parent):
        body = self.create_card(parent, "ACTIONS")
        
        self.progress = ttk.Progressbar(body, mode='indeterminate', 
                                        style="Custom.Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 15))
        
        tk.Button(body, text="LOAD FOLDER", bg=self.colors['accent'],
                 fg=self.colors['text'], activebackground=self.colors['accent_hover'],
                 relief=tk.FLAT, font=('Segoe UI', 11, 'bold'), cursor='hand2',
                 command=self.load_folder).pack(fill=tk.X, ipady=12)
        
        btn_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        tk.Button(btn_frame, text="Save PNG", bg=self.colors['bg_light'],
                 fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 9),
                 cursor='hand2', width=12, command=self.save_image).pack(side=tk.LEFT, ipady=8)
        
        tk.Button(btn_frame, text="Compare", bg=self.colors['bg_light'],
                 fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 9),
                 cursor='hand2', width=12, command=self.compare_products).pack(side=tk.RIGHT, ipady=8)
    
    def create_info_card(self, parent):
        body = self.create_card(parent, "PRODUCT INFO")
        
        self.info_text = tk.Text(body, height=8, bg=self.colors['bg_light'],
                                 fg=self.colors['text_secondary'], relief=tk.FLAT,
                                 font=('Consolas', 9), state=tk.DISABLED)
        self.info_text.pack(fill=tk.X)
        self.update_info("No product loaded.\n\nSelect a folder with\nASF InSAR GeoTIFFs.")
    
    def create_visualization_panel(self, parent):
        viz_header = tk.Frame(parent, bg=self.colors['bg_light'], height=50)
        viz_header.pack(fill=tk.X)
        viz_header.pack_propagate(False)
        
        tk.Label(viz_header, text="VISUALIZATION", bg=self.colors['bg_light'],
                fg=self.colors['text'], font=('Segoe UI', 12, 'bold')).pack(side=tk.LEFT, padx=15, pady=12)
        
        self.title_label = tk.Label(viz_header, text="", bg=self.colors['bg_light'],
                                    fg=self.colors['accent'], font=('Segoe UI', 10))
        self.title_label.pack(side=tk.RIGHT, padx=15, pady=12)
        
        plt.style.use('dark_background')
        
        self.fig = Figure(figsize=(10, 8), facecolor=self.colors['bg_dark'])
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(self.colors['bg_medium'])
        self.ax.text(0.5, 0.5, 'ASF InSAR Product Viewer\n\nSelect a folder to begin',
                    ha='center', va='center', fontsize=14, color=self.colors['text_secondary'])
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        
        canvas_frame = tk.Frame(parent, bg=self.colors['bg_dark'])
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=canvas_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        toolbar_frame = tk.Frame(parent, bg=self.colors['bg_medium'])
        toolbar_frame.pack(fill=tk.X)
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()
    
    def update_info(self, text):
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, text)
        self.info_text.config(state=tk.DISABLED)
    
    def browse_folder(self):
        initial_dir = os.path.expanduser("~")
        if os.path.exists("C:/Users"):
            initial_dir = "C:/Users"
        
        folder = filedialog.askdirectory(title="Select InSAR Product Folder",
                                         initialdir=initial_dir)
        if folder:
            self.folder_path.set(folder)
            self.status_var.set(f"Selected: {os.path.basename(folder)}")
            self.load_folder()
    
    def load_folder(self):
        folder = self.folder_path.get()
        if not folder:
            messagebox.showerror("Error", "Please select a folder!")
            return
        if not os.path.isdir(folder):
            messagebox.showerror("Error", f"Folder not found: {folder}")
            return
        
        try:
            self.progress.start(10)
            self.status_var.set("Scanning for GeoTIFF files...")
            self.root.update()
            
            # Find all TIF files
            self.tif_files = []
            for ext in ['*.tif', '*.tiff', '*.TIF', '*.TIFF']:
                self.tif_files.extend(glob.glob(os.path.join(folder, ext)))
            
            if not self.tif_files:
                messagebox.showwarning("Warning", "No GeoTIFF files found in this folder!")
                self.progress.stop()
                return
            
            # Sort and populate listbox
            self.tif_files.sort()
            self.product_listbox.delete(0, tk.END)
            
            for tif_path in self.tif_files:
                fname = os.path.basename(tif_path)
                product_type = self.detect_product_type(fname)
                
                if product_type != 'unknown':
                    display_name = f"[{product_type.upper()}] {fname[:35]}..."
                else:
                    display_name = fname[:45] + "..." if len(fname) > 45 else fname
                
                self.product_listbox.insert(tk.END, display_name)
            
            info_text = f"Folder: {os.path.basename(folder)}\n"
            info_text += f"Products found: {len(self.tif_files)}\n\n"
            info_text += "Click a product to visualize."
            self.update_info(info_text)
            
            self.status_var.set(f"Found {len(self.tif_files)} GeoTIFF products")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load folder:\n{str(e)}")
        finally:
            self.progress.stop()
    
    def on_product_select(self, event):
        selection = self.product_listbox.curselection()
        if selection:
            idx = selection[0]
            self.display_product(self.tif_files[idx])
    
    def read_geotiff(self, filepath):
        """Read GeoTIFF using rasterio or GDAL"""
        if HAS_RASTERIO:
            with rasterio.open(filepath) as src:
                data = src.read(1).astype(np.float64)
                self.geo_transform = src.transform
                self.projection = src.crs
                nodata = src.nodata
                
                if nodata is not None:
                    data = np.where(data == nodata, np.nan, data)
                
                return data
                
        elif HAS_GDAL:
            ds = gdal.Open(filepath)
            if ds is None:
                raise Exception(f"Could not open: {filepath}")
            
            data = ds.ReadAsArray().astype(np.float64)
            self.geo_transform = ds.GetGeoTransform()
            self.projection = ds.GetProjection()
            nodata = ds.GetRasterBand(1).GetNoDataValue()
            ds = None
            
            if nodata is not None:
                data = np.where(data == nodata, np.nan, data)
            
            return data
        else:
            raise Exception("No GeoTIFF reader available. Install rasterio.")
    
    def display_product(self, filepath):
        try:
            self.progress.start(10)
            fname = os.path.basename(filepath)
            self.status_var.set(f"Loading {fname}...")
            self.root.update()
            
            # Read data
            data = self.read_geotiff(filepath)
            self.current_data = data
            self.current_file = filepath
            
            # Handle multi-band
            if len(data.shape) == 3:
                data = data[0]
                self.current_data = data
            
            # Detect product type
            product_type = self.detect_product_type(fname)
            
            # Get colormap
            if self.colormap_var.get() == "auto":
                cmap_name = self.get_default_colormap(product_type)
            else:
                cmap_name = self.colormap_var.get()
            
            cmap = self.get_colormap(cmap_name)
            
            # Calculate display range
            valid_data = data[np.isfinite(data)]
            if len(valid_data) > 0:
                vmin, vmax = np.percentile(valid_data, [2, 98])
            else:
                vmin, vmax = 0, 1
            
            # User overrides
            if self.vmin_var.get() != "auto":
                try:
                    vmin = float(self.vmin_var.get())
                except:
                    pass
            if self.vmax_var.get() != "auto":
                try:
                    vmax = float(self.vmax_var.get())
                except:
                    pass
            
            # Plot
            self.fig.clear()
            self.ax = self.fig.add_subplot(111)
            self.ax.set_facecolor(self.colors['bg_medium'])
            
            im = self.ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax)
            
            # Title
            title_map = {
                'wrapped_phase': 'Wrapped Interferometric Phase',
                'unwrapped_phase': 'Unwrapped Phase',
                'coherence': 'Coherence',
                'amplitude': 'Radar Amplitude',
                'dem': 'Digital Elevation Model',
                'displacement': 'Line-of-Sight Displacement',
                'vertical_disp': 'Vertical Displacement',
                'incidence': 'Incidence Angle',
                'azimuth': 'Azimuth Angle'
            }
            
            title = title_map.get(product_type, product_type.upper())
            self.ax.set_title(title, fontsize=12, color=self.colors['text'], fontweight='bold')
            self.ax.set_xlabel('Range (pixels)', color=self.colors['text_secondary'])
            self.ax.set_ylabel('Azimuth (pixels)', color=self.colors['text_secondary'])
            self.ax.tick_params(colors=self.colors['text_secondary'])
            
            # Colorbar
            cbar_labels = {
                'wrapped_phase': 'Phase (rad)',
                'unwrapped_phase': 'Phase (rad)',
                'coherence': 'Coherence',
                'amplitude': 'Amplitude',
                'dem': 'Elevation (m)',
                'displacement': 'Displacement (m)',
                'vertical_disp': 'Displacement (m)',
                'incidence': 'Angle (deg)',
                'azimuth': 'Angle (deg)'
            }
            
            cbar = self.fig.colorbar(im, ax=self.ax, shrink=0.8)
            cbar.set_label(cbar_labels.get(product_type, 'Value'), 
                          color=self.colors['text_secondary'])
            cbar.ax.yaxis.set_tick_params(color=self.colors['text_secondary'])
            
            self.fig.tight_layout()
            self.canvas.draw()
            
            self.title_label.config(text=f"{product_type.upper()} | {data.shape[1]}x{data.shape[0]} px")
            
            # Info
            info_text = f"File: {fname[:30]}...\n" if len(fname) > 30 else f"File: {fname}\n"
            info_text += f"Type: {product_type}\n"
            info_text += f"Shape: {data.shape}\n"
            info_text += f"Range: {np.nanmin(data):.4f} to {np.nanmax(data):.4f}\n"
            info_text += f"Display: {vmin:.4f} to {vmax:.4f}\n"
            info_text += f"Colormap: {cmap_name}"
            self.update_info(info_text)
            
            self.status_var.set(f"Displaying: {title}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to display:\n{str(e)}")
        finally:
            self.progress.stop()
    
    def on_colormap_change(self, event=None):
        if self.current_file:
            self.display_product(self.current_file)
    
    def apply_settings(self):
        if self.current_file:
            self.display_product(self.current_file)
    
    def save_image(self):
        if self.current_data is None:
            messagebox.showerror("Error", "No data to save!")
            return
        
        save_path = filedialog.asksaveasfilename(
            title="Save Image",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("PDF files", "*.pdf")]
        )
        
        if save_path:
            try:
                self.fig.savefig(save_path, dpi=300, bbox_inches='tight', 
                               facecolor=self.colors['bg_dark'])
                messagebox.showinfo("Success", f"Saved to:\n{save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {str(e)}")
    
    def compare_products(self):
        """Compare multiple products side by side"""
        if len(self.tif_files) < 2:
            messagebox.showwarning("Warning", "Need at least 2 products!")
            return
        
        compare_win = tk.Toplevel(self.root)
        compare_win.title("Product Comparison")
        compare_win.geometry("1400x800")
        compare_win.configure(bg=self.colors['bg_dark'])
        
        # Selection
        select_frame = tk.Frame(compare_win, bg=self.colors['bg_medium'])
        select_frame.pack(fill=tk.X, padx=20, pady=20)
        
        tk.Label(select_frame, text="Select products to compare (max 4):", 
                bg=self.colors['bg_medium'], fg=self.colors['text'],
                font=('Segoe UI', 11, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        self.compare_vars = []
        for i, tif_path in enumerate(self.tif_files[:8]):
            var = tk.BooleanVar()
            fname = os.path.basename(tif_path)
            cb = tk.Checkbutton(select_frame, text=fname[:55], variable=var,
                               bg=self.colors['bg_medium'], fg=self.colors['text'],
                               selectcolor=self.colors['bg_light'],
                               activebackground=self.colors['bg_medium'],
                               font=('Consolas', 9))
            cb.pack(anchor=tk.W)
            self.compare_vars.append((var, tif_path))
        
        tk.Button(select_frame, text="Compare Selected", bg=self.colors['accent'],
                 fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 10, 'bold'),
                 command=lambda: self.show_comparison(compare_win)).pack(pady=15)
        
        self.compare_fig_frame = tk.Frame(compare_win, bg=self.colors['bg_dark'])
        self.compare_fig_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
    
    def show_comparison(self, window):
        selected = [(path, var.get()) for var, path in self.compare_vars if var.get()]
        
        if len(selected) < 2:
            messagebox.showwarning("Warning", "Select at least 2 products!")
            return
        
        selected = selected[:4]
        
        for widget in self.compare_fig_frame.winfo_children():
            widget.destroy()
        
        n = len(selected)
        fig = Figure(figsize=(14, 6), facecolor=self.colors['bg_dark'])
        
        for i, (path, _) in enumerate(selected):
            ax = fig.add_subplot(1, n, i+1)
            ax.set_facecolor(self.colors['bg_medium'])
            
            try:
                data = self.read_geotiff(path)
                if len(data.shape) == 3:
                    data = data[0]
                
                fname = os.path.basename(path)
                product_type = self.detect_product_type(fname)
                cmap = self.get_colormap(self.get_default_colormap(product_type))
                
                valid_data = data[np.isfinite(data)]
                if len(valid_data) > 0:
                    vmin, vmax = np.percentile(valid_data, [2, 98])
                else:
                    vmin, vmax = 0, 1
                
                ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax)
                ax.set_title(product_type.upper(), fontsize=10, 
                           color=self.colors['text'], fontweight='bold')
                ax.set_xticks([])
                ax.set_yticks([])
                
            except Exception as e:
                ax.text(0.5, 0.5, f"Error:\n{str(e)}", ha='center', va='center',
                       color=self.colors['accent'])
        
        fig.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=self.compare_fig_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)


def main():
    root = tk.Tk()
    app = ASFInSARViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()