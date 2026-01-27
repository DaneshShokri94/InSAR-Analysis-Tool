import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap
import os
import h5py

class InSARViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("InSAR Data Viewer Pro v1.0")
        self.root.geometry("1500x900")
        self.root.minsize(1200, 800)
        
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
        
        self.file_path = tk.StringVar()
        self.status_var = tk.StringVar(value="Welcome! Load an InSAR HDF5 file to begin.")
        self.colormap_var = tk.StringVar(value="jet")
        
        self.hdf5_file = None
        self.datasets = {}
        self.current_data = None
        self.dataset_list = []
        
        self.custom_cmaps = self.create_insar_colormaps()
        
        self.setup_styles()
        self.create_widgets()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_insar_colormaps(self):
        custom_cmaps = {}
        phase_colors = ['#ff0000', '#ffff00', '#00ff00', '#00ffff', '#0000ff', '#ff00ff', '#ff0000']
        custom_cmaps['phase'] = LinearSegmentedColormap.from_list('phase', phase_colors, N=256)
        coh_colors = ['#000000', '#1a1a2e', '#16213e', '#0f3460', '#e94560', '#ff6b6b', '#ffffff']
        custom_cmaps['coherence'] = LinearSegmentedColormap.from_list('coherence', coh_colors, N=256)
        return custom_cmaps
    
    def get_colormap(self, name):
        if name in self.custom_cmaps:
            return self.custom_cmaps[name]
        else:
            return plt.get_cmap(name)
    
    def on_closing(self):
        if self.hdf5_file:
            self.hdf5_file.close()
        self.root.destroy()
    
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
        
        header_frame = ttk.Frame(main_container, style='Dark.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(header_frame, text="🛰️ InSAR Data Viewer Pro", style='Title.TLabel').pack(side=tk.LEFT)
        ttk.Label(header_frame, text="HDF5 InSAR Product Visualization", style='Subtitle.TLabel').pack(side=tk.LEFT, padx=(20, 0), pady=(10, 0))
        
        left_panel = ttk.Frame(main_container, style='Dark.TFrame', width=380)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        left_panel.pack_propagate(False)
        
        self.create_file_card(left_panel)
        self.create_dataset_card(left_panel)
        self.create_options_card(left_panel)
        self.create_actions_card(left_panel)
        self.create_info_card(left_panel)
        
        right_panel = ttk.Frame(main_container, style='Dark.TFrame')
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.create_visualization_panel(right_panel)
        
        status_frame = ttk.Frame(self.root, style='Dark.TFrame')
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(status_frame, textvariable=self.status_var, style='Status.TLabel').pack(fill=tk.X)
    
    def create_card(self, parent, title):
        card = tk.Frame(parent, bg=self.colors['bg_medium'], highlightbackground=self.colors['border'], highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 15))
        header = tk.Frame(card, bg=self.colors['bg_light'], height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=title, bg=self.colors['bg_light'], fg=self.colors['text'], font=('Segoe UI', 11, 'bold')).pack(side=tk.LEFT, padx=15, pady=8)
        body = tk.Frame(card, bg=self.colors['bg_medium'])
        body.pack(fill=tk.X, padx=15, pady=15)
        return body
    
    def create_file_card(self, parent):
        body = self.create_card(parent, "📁 FILE SELECTION")
        tk.Label(body, text="InSAR HDF5 File:", bg=self.colors['bg_medium'], fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(anchor=tk.W)
        file_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        file_frame.pack(fill=tk.X, pady=(5, 0))
        tk.Entry(file_frame, textvariable=self.file_path, bg=self.colors['bg_light'], fg=self.colors['text'], insertbackground=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 10))
        tk.Button(file_frame, text="Browse", bg=self.colors['accent'], fg=self.colors['text'], activebackground=self.colors['accent_hover'], relief=tk.FLAT, font=('Segoe UI', 9, 'bold'), cursor='hand2', command=self.browse_file).pack(side=tk.RIGHT, ipadx=15, ipady=5)
    
    def create_dataset_card(self, parent):
        body = self.create_card(parent, "📊 DATASETS")
        list_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        list_frame.pack(fill=tk.X)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.dataset_listbox = tk.Listbox(list_frame, height=8, bg=self.colors['bg_light'], fg=self.colors['text'], selectbackground=self.colors['accent'], selectforeground=self.colors['text'], relief=tk.FLAT, font=('Consolas', 9), yscrollcommand=scrollbar.set)
        self.dataset_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.dataset_listbox.bind('<<ListboxSelect>>', self.on_dataset_select)
        scrollbar.config(command=self.dataset_listbox.yview)
    
    def create_options_card(self, parent):
        body = self.create_card(parent, "🎨 DISPLAY OPTIONS")
        options_grid = tk.Frame(body, bg=self.colors['bg_medium'])
        options_grid.pack(fill=tk.X)
        
        tk.Label(options_grid, text="Colormap:", bg=self.colors['bg_medium'], fg=self.colors['text_secondary'], font=('Segoe UI', 9)).grid(row=0, column=0, sticky=tk.W, pady=5)
        colormaps = ["jet", "viridis", "plasma", "inferno", "magma", "cividis", "hsv", "twilight", "RdBu_r", "seismic", "phase", "coherence", "gray"]
        cmap_combo = ttk.Combobox(options_grid, textvariable=self.colormap_var, values=colormaps, width=15, state="readonly")
        cmap_combo.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        cmap_combo.bind('<<ComboboxSelected>>', self.update_colormap)
        
        self.vmin_var = tk.StringVar(value="auto")
        self.vmax_var = tk.StringVar(value="auto")
        
        tk.Label(options_grid, text="Min Value:", bg=self.colors['bg_medium'], fg=self.colors['text_secondary'], font=('Segoe UI', 9)).grid(row=1, column=0, sticky=tk.W, pady=5)
        tk.Entry(options_grid, textvariable=self.vmin_var, width=12, bg=self.colors['bg_light'], fg=self.colors['text'], insertbackground=self.colors['text'], relief=tk.FLAT).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        tk.Label(options_grid, text="Max Value:", bg=self.colors['bg_medium'], fg=self.colors['text_secondary'], font=('Segoe UI', 9)).grid(row=2, column=0, sticky=tk.W, pady=5)
        tk.Entry(options_grid, textvariable=self.vmax_var, width=12, bg=self.colors['bg_light'], fg=self.colors['text'], insertbackground=self.colors['text'], relief=tk.FLAT).grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        tk.Button(options_grid, text="Apply", bg=self.colors['bg_light'], fg=self.colors['text'], activebackground=self.colors['border'], relief=tk.FLAT, font=('Segoe UI', 9), cursor='hand2', width=10, command=self.apply_settings).grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=10)
    
    def create_actions_card(self, parent):
        body = self.create_card(parent, "🚀 ACTIONS")
        self.progress = ttk.Progressbar(body, mode='indeterminate', style="Custom.Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 15))
        
        tk.Button(body, text="▶ LOAD FILE", bg=self.colors['accent'], fg=self.colors['text'], activebackground=self.colors['accent_hover'], relief=tk.FLAT, font=('Segoe UI', 11, 'bold'), cursor='hand2', command=self.load_file).pack(fill=tk.X, ipady=12)
        
        btn_frame = tk.Frame(body, bg=self.colors['bg_medium'])
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        tk.Button(btn_frame, text="💾 Save", bg=self.colors['bg_light'], fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 9), cursor='hand2', width=12, command=self.save_image).pack(side=tk.LEFT, ipady=8)
        tk.Button(btn_frame, text="📤 Export", bg=self.colors['bg_light'], fg=self.colors['text'], relief=tk.FLAT, font=('Segoe UI', 9), cursor='hand2', width=12, command=self.export_geotiff).pack(side=tk.RIGHT, ipady=8)
    
    def create_info_card(self, parent):
        body = self.create_card(parent, "ℹ️ DATA INFO")
        self.info_text = tk.Text(body, height=8, bg=self.colors['bg_light'], fg=self.colors['text_secondary'], relief=tk.FLAT, font=('Consolas', 9), state=tk.DISABLED)
        self.info_text.pack(fill=tk.X)
        self.update_info("No data loaded.\n\nLoad an HDF5 file to see\ndataset information.")
    
    def create_visualization_panel(self, parent):
        viz_header = tk.Frame(parent, bg=self.colors['bg_light'], height=50)
        viz_header.pack(fill=tk.X)
        viz_header.pack_propagate(False)
        tk.Label(viz_header, text="📊 VISUALIZATION", bg=self.colors['bg_light'], fg=self.colors['text'], font=('Segoe UI', 12, 'bold')).pack(side=tk.LEFT, padx=15, pady=12)
        
        plt.style.use('dark_background')
        
        self.fig = Figure(figsize=(10, 8), facecolor=self.colors['bg_dark'])
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(self.colors['bg_medium'])
        self.ax.text(0.5, 0.5, 'InSAR Data\n\nNo data loaded', ha='center', va='center', fontsize=14, color=self.colors['text_secondary'])
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
    
    def browse_file(self):
        filepath = filedialog.askopenfilename(title="Select InSAR HDF5 File", filetypes=[("HDF5 files", "*.h5 *.hdf5 *.he5"), ("All files", "*.*")], initialdir="C:/Users/danes/Desktop/ice")
        if filepath:
            self.file_path.set(filepath)
            self.status_var.set(f"✓ Selected: {os.path.basename(filepath)}")
            self.load_file()
    
    def load_file(self):
        filepath = self.file_path.get()
        if not filepath:
            messagebox.showerror("Error", "Please select an HDF5 file!")
            return
        if not os.path.exists(filepath):
            messagebox.showerror("Error", f"File not found: {filepath}")
            return
        
        try:
            self.progress.start(10)
            self.status_var.set("⏳ Loading HDF5 file...")
            
            if self.hdf5_file:
                self.hdf5_file.close()
            
            self.hdf5_file = h5py.File(filepath, 'r')
            self.datasets = {}
            self.dataset_list = []
            self.find_datasets(self.hdf5_file, "")
            
            self.dataset_listbox.delete(0, tk.END)
            for ds_name in self.dataset_list:
                self.dataset_listbox.insert(tk.END, ds_name)
            
            info_text = f"File: {os.path.basename(filepath)}\nDatasets: {len(self.dataset_list)}\n\nSelect a dataset to visualize."
            self.update_info(info_text)
            self.status_var.set(f"✓ Loaded! Found {len(self.dataset_list)} datasets.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file:\n{str(e)}")
        finally:
            self.progress.stop()
    
    def find_datasets(self, group, path):
        for key in group.keys():
            item = group[key]
            item_path = f"{path}/{key}" if path else key
            if isinstance(item, h5py.Dataset):
                if len(item.shape) >= 2:
                    self.dataset_list.append(item_path)
                    self.datasets[item_path] = item
            elif isinstance(item, h5py.Group):
                self.find_datasets(item, item_path)
    
    def on_dataset_select(self, event):
        selection = self.dataset_listbox.curselection()
        if selection:
            ds_name = self.dataset_list[selection[0]]
            self.display_dataset(ds_name)
    
    def display_dataset(self, ds_name):
        try:
            self.progress.start(10)
            self.status_var.set(f"⏳ Loading {ds_name}...")
            
            ds = self.datasets[ds_name]
            data = ds[:]
            original_shape = data.shape
            
            # Handle complex data
            if np.iscomplexobj(data):
                data = np.angle(data)
                data_type = "Phase (Complex)"
            else:
                data = data.astype(np.float64)
                data_type = "Real"
            
            # Squeeze out dimensions of size 1 (handles shapes like (1, 40, 40, 1))
            data = np.squeeze(data)
            
            # If still more than 2D, take first slice
            while len(data.shape) > 2:
                data = data[0]
                data_type += " (slice)"
            
            self.current_data = data
            
            # Clear and plot
            self.fig.clear()
            self.ax = self.fig.add_subplot(111)
            self.ax.set_facecolor(self.colors['bg_medium'])
            
            cmap = self.get_colormap(self.colormap_var.get())
            
            valid_data = self.current_data[np.isfinite(self.current_data)]
            if len(valid_data) > 0:
                vmin, vmax = np.percentile(valid_data, [2, 98])
            else:
                vmin, vmax = 0, 1
            
            if self.vmin_var.get() != "auto":
                try: vmin = float(self.vmin_var.get())
                except: pass
            if self.vmax_var.get() != "auto":
                try: vmax = float(self.vmax_var.get())
                except: pass
            
            im = self.ax.imshow(self.current_data, cmap=cmap, vmin=vmin, vmax=vmax)
            self.ax.set_title(f"📊 {ds_name}", fontsize=12, color=self.colors['text'], fontweight='bold')
            self.ax.set_xlabel('Range (pixels)', color=self.colors['text_secondary'])
            self.ax.set_ylabel('Azimuth (pixels)', color=self.colors['text_secondary'])
            self.ax.tick_params(colors=self.colors['text_secondary'])
            
            cbar = self.fig.colorbar(im, ax=self.ax, shrink=0.8)
            cbar.ax.yaxis.set_tick_params(color=self.colors['text_secondary'])
            
            self.fig.tight_layout()
            self.canvas.draw()
            
            info_text = f"Dataset: {ds_name}\nOriginal Shape: {original_shape}\nDisplay Shape: {self.current_data.shape}\nType: {ds.dtype}\nData: {data_type}\nMin: {vmin:.4f}\nMax: {vmax:.4f}"
            self.update_info(info_text)
            self.status_var.set(f"✓ Displaying: {ds_name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to display dataset:\n{str(e)}")
        finally:
            self.progress.stop()
    
    def update_colormap(self, event=None):
        if self.current_data is not None:
            selection = self.dataset_listbox.curselection()
            if selection:
                self.display_dataset(self.dataset_list[selection[0]])
    
    def apply_settings(self):
        if self.current_data is not None:
            selection = self.dataset_listbox.curselection()
            if selection:
                self.display_dataset(self.dataset_list[selection[0]])
    
    def save_image(self):
        if self.current_data is None:
            messagebox.showerror("Error", "No data to save!")
            return
        save_path = filedialog.asksaveasfilename(title="Save Image", defaultextension=".png", filetypes=[("PNG files", "*.png"), ("PDF files", "*.pdf")])
        if save_path:
            try:
                self.fig.savefig(save_path, dpi=300, bbox_inches='tight', facecolor=self.colors['bg_dark'])
                messagebox.showinfo("Success", f"Image saved to:\n{save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {str(e)}")
    
    def export_geotiff(self):
        if self.current_data is None:
            messagebox.showerror("Error", "No data to export!")
            return
        try:
            from osgeo import gdal
            save_path = filedialog.asksaveasfilename(title="Export GeoTIFF", defaultextension=".tif", filetypes=[("GeoTIFF files", "*.tif *.tiff")])
            if save_path:
                driver = gdal.GetDriverByName('GTiff')
                rows, cols = self.current_data.shape
                out_ds = driver.Create(save_path, cols, rows, 1, gdal.GDT_Float32)
                out_ds.GetRasterBand(1).WriteArray(self.current_data)
                out_ds = None
                messagebox.showinfo("Success", f"GeoTIFF exported to:\n{save_path}")
        except ImportError:
            messagebox.showwarning("Warning", "GDAL not available. Use 'Save' for PNG instead.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = InSARViewerApp(root)
    root.mainloop()