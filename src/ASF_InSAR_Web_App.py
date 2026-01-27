"""
ASF InSAR Product Viewer - Web Application
==========================================
Professional web-based viewer for ASF On-Demand InSAR GeoTIFF products.
Built with Streamlit for easy deployment.

Usage:
    streamlit run ASF_InSAR_Web_App.py

Author: Danesh Shokri
Version: 1.1
"""

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import plotly.graph_objects as go
import os
import tempfile
import zipfile
from io import BytesIO

# Try to import rasterio
try:
    import rasterio
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

# Page configuration
st.set_page_config(
    page_title="ASF InSAR Viewer",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    }
    [data-testid="stSidebar"] {
        background: #16213e;
    }
    h1, h2, h3 {
        color: #e94560 !important;
    }
    .stButton > button {
        background-color: #e94560;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 10px 20px;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #ff6b6b;
    }
    .info-box {
        background-color: #0f3460;
        border-left: 4px solid #e94560;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


# Custom colormaps
def create_insar_colormaps():
    """Create custom colormaps for InSAR products"""
    cmaps = {}
    phase_colors = ['#ff0000', '#ffff00', '#00ff00', '#00ffff', '#0000ff', '#ff00ff', '#ff0000']
    cmaps['phase'] = LinearSegmentedColormap.from_list('phase', phase_colors, N=256)
    disp_colors = ['#0000ff', '#4444ff', '#8888ff', '#ffffff', '#ff8888', '#ff4444', '#ff0000']
    cmaps['displacement'] = LinearSegmentedColormap.from_list('displacement', disp_colors, N=256)
    dem_colors = ['#006400', '#228B22', '#90EE90', '#FFFF00', '#FFA500', '#8B4513', '#FFFFFF']
    cmaps['terrain'] = LinearSegmentedColormap.from_list('terrain_custom', dem_colors, N=256)
    return cmaps

CUSTOM_CMAPS = create_insar_colormaps()


def detect_product_type(filename):
    """Detect InSAR product type from filename"""
    fname_lower = filename.lower()
    patterns = {
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
    for product_type, keywords in patterns.items():
        for keyword in keywords:
            if keyword in fname_lower:
                return product_type
    return 'unknown'


def get_default_colormap(product_type):
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


def get_colormap(name):
    """Get colormap by name"""
    if name in CUSTOM_CMAPS:
        return CUSTOM_CMAPS[name]
    try:
        return plt.get_cmap(name)
    except:
        return plt.get_cmap('viridis')


def read_geotiff(file_bytes, filename):
    """Read GeoTIFF from uploaded bytes"""
    if not HAS_RASTERIO:
        return None, None, "Rasterio not installed"
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.tif') as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    
    try:
        with rasterio.open(tmp_path) as src:
            data = src.read(1).astype(np.float64)
            nodata = src.nodata
            meta = {
                'crs': str(src.crs) if src.crs else 'Unknown',
                'transform': src.transform,
                'width': src.width,
                'height': src.height,
                'bounds': src.bounds
            }
            if nodata is not None:
                data = np.where(data == nodata, np.nan, data)
            return data, meta, None
    except Exception as e:
        return None, None, str(e)
    finally:
        os.unlink(tmp_path)


def extract_zip(zip_bytes):
    """Extract TIF files from uploaded ZIP"""
    tif_files = {}
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = os.path.join(tmp_dir, 'upload.zip')
        with open(zip_path, 'wb') as f:
            f.write(zip_bytes)
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.lower().endswith(('.tif', '.tiff')):
                    zf.extract(name, tmp_dir)
                    extracted_path = os.path.join(tmp_dir, name)
                    try:
                        with rasterio.open(extracted_path) as src:
                            data = src.read(1).astype(np.float64)
                            nodata = src.nodata
                            if nodata is not None:
                                data = np.where(data == nodata, np.nan, data)
                            tif_files[os.path.basename(name)] = {
                                'data': data,
                                'crs': str(src.crs) if src.crs else 'Unknown',
                                'shape': data.shape
                            }
                    except Exception as e:
                        st.warning(f"Could not read {name}: {e}")
    return tif_files


def create_matplotlib_figure(data, title, cmap_name, vmin, vmax):
    """Create matplotlib figure for display"""
    fig, ax = plt.subplots(figsize=(10, 8))
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#16213e')
    
    cmap = get_colormap(cmap_name)
    im = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax)
    
    ax.set_title(title, fontsize=14, color='white', fontweight='bold')
    ax.set_xlabel('Range (pixels)', color='#a0a0a0')
    ax.set_ylabel('Azimuth (pixels)', color='#a0a0a0')
    ax.tick_params(colors='#a0a0a0')
    
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.yaxis.set_tick_params(color='#a0a0a0')
    plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='#a0a0a0')
    
    plt.tight_layout()
    return fig


def create_plotly_figure(data, title, colorscale, vmin, vmax):
    """Create interactive Plotly figure - FIXED VERSION"""
    fig = go.Figure(data=go.Heatmap(
        z=data,
        colorscale=colorscale,
        zmin=vmin,
        zmax=vmax,
        colorbar=dict(
            title=dict(
                text="Value",
                font=dict(color='white')
            ),
            tickfont=dict(color='white')
        )
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(color='#e94560', size=18)),
        paper_bgcolor='#1a1a2e',
        plot_bgcolor='#16213e',
        xaxis=dict(
            title='Range (pixels)',
            color='#a0a0a0',
            gridcolor='#2d3748'
        ),
        yaxis=dict(
            title='Azimuth (pixels)',
            color='#a0a0a0',
            gridcolor='#2d3748',
            autorange='reversed'
        ),
        height=600
    )
    
    return fig


# Plotly colorscale mapping
PLOTLY_COLORSCALES = {
    'viridis': 'Viridis',
    'plasma': 'Plasma',
    'inferno': 'Inferno',
    'magma': 'Magma',
    'gray': 'Greys',
    'jet': 'Jet',
    'hsv': 'HSV',
    'RdBu_r': 'RdBu_r',
    'seismic': 'RdBu',
    'phase': 'Rainbow',
    'displacement': 'RdBu_r',
    'terrain': 'Earth',
    'coherence': 'Greys'
}


def process_and_display(data, filename, meta, selected_cmap, auto_range, manual_vmin, manual_vmax, viz_type):
    """Process and display the data"""
    
    product_type = detect_product_type(filename)
    
    if selected_cmap == "auto":
        cmap_name = get_default_colormap(product_type)
    else:
        cmap_name = selected_cmap
    
    valid_data = data[np.isfinite(data)]
    if len(valid_data) > 0:
        if auto_range:
            vmin, vmax = np.percentile(valid_data, [2, 98])
        else:
            vmin = manual_vmin if manual_vmin is not None else np.nanmin(data)
            vmax = manual_vmax if manual_vmax is not None else np.nanmax(data)
    else:
        vmin, vmax = 0, 1
    
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
    title = title_map.get(product_type, filename)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Product Type", product_type.upper())
    with col2:
        st.metric("Dimensions", f"{data.shape[1]} × {data.shape[0]}")
    with col3:
        st.metric("Min Value", f"{np.nanmin(data):.4f}")
    with col4:
        st.metric("Max Value", f"{np.nanmax(data):.4f}")
    
    if viz_type == "Interactive (Plotly)":
        plotly_cmap = PLOTLY_COLORSCALES.get(cmap_name, 'Viridis')
        fig = create_plotly_figure(data, title, plotly_cmap, vmin, vmax)
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig = create_matplotlib_figure(data, title, cmap_name, vmin, vmax)
        st.pyplot(fig)
    
    with st.expander("📋 Detailed Information"):
        st.markdown(f"""
        | Property | Value |
        |----------|-------|
        | **Filename** | {filename} |
        | **Product Type** | {product_type} |
        | **Width** | {data.shape[1]} pixels |
        | **Height** | {data.shape[0]} pixels |
        | **CRS** | {meta.get('crs', 'Unknown')} |
        | **Data Min** | {np.nanmin(data):.6f} |
        | **Data Max** | {np.nanmax(data):.6f} |
        | **Data Mean** | {np.nanmean(data):.6f} |
        | **Display Range** | {vmin:.4f} to {vmax:.4f} |
        | **Colormap** | {cmap_name} |
        """)
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        fig_dl = create_matplotlib_figure(data, title, cmap_name, vmin, vmax)
        buf = BytesIO()
        fig_dl.savefig(buf, format='png', dpi=300, bbox_inches='tight', facecolor='#1a1a2e')
        buf.seek(0)
        plt.close(fig_dl)
        
        st.download_button(
            label="📥 Download PNG",
            data=buf,
            file_name=f"{product_type}_{filename.replace('.tif', '')}.png",
            mime="image/png"
        )
    
    with col2:
        csv_buf = BytesIO()
        np.savetxt(csv_buf, data, delimiter=',', fmt='%.6f')
        csv_buf.seek(0)
        
        st.download_button(
            label="📥 Download CSV Data",
            data=csv_buf.getvalue(),
            file_name=f"{product_type}_{filename.replace('.tif', '')}.csv",
            mime="text/csv"
        )


def main():
    # Header
    st.markdown("""
    <h1 style='text-align: center;'>🛰️ ASF InSAR Product Viewer</h1>
    <p style='text-align: center; color: #a0a0a0;'>
        Web-based visualization tool for ASF On-Demand InSAR GeoTIFF products
    </p>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Check rasterio
    if not HAS_RASTERIO:
        st.error("⚠️ Rasterio is required. Install with: `pip install rasterio`")
        return
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📁 File Upload")
        
        upload_type = st.radio(
            "Upload type:",
            ["Single GeoTIFF", "ZIP Archive", "Multiple GeoTIFFs"],
            index=0
        )
        
        if upload_type == "Single GeoTIFF":
            uploaded_file = st.file_uploader(
                "Choose a GeoTIFF file",
                type=['tif', 'tiff']
            )
        elif upload_type == "ZIP Archive":
            uploaded_file = st.file_uploader(
                "Choose a ZIP file",
                type=['zip']
            )
        else:
            uploaded_file = st.file_uploader(
                "Choose GeoTIFF files",
                type=['tif', 'tiff'],
                accept_multiple_files=True
            )
        
        st.markdown("---")
        st.markdown("## 🎨 Display Options")
        
        colormap_options = [
            "auto", "phase", "displacement", "terrain", "coherence",
            "viridis", "plasma", "inferno", "magma", "gray",
            "jet", "hsv", "RdBu_r", "seismic"
        ]
        selected_cmap = st.selectbox("Colormap", colormap_options, index=0)
        
        st.markdown("### Value Range")
        auto_range = st.checkbox("Auto range (2-98 percentile)", value=True)
        
        manual_vmin = None
        manual_vmax = None
        if not auto_range:
            col1, col2 = st.columns(2)
            with col1:
                manual_vmin = st.number_input("Min", value=0.0)
            with col2:
                manual_vmax = st.number_input("Max", value=1.0)
        
        st.markdown("---")
        st.markdown("## 📊 Visualization")
        
        viz_type = st.radio(
            "Plot type:",
            ["Interactive (Plotly)", "Static (Matplotlib)"],
            index=0
        )
        
        st.markdown("---")
        st.markdown("### ℹ️ About")
        st.info("""
        Supported products:
        - Wrapped Phase
        - Unwrapped Phase
        - Coherence
        - Amplitude
        - DEM
        - Displacement Maps
        """)
    
    # Main content
    if upload_type == "Single GeoTIFF" and uploaded_file is not None:
        with st.spinner("Loading GeoTIFF..."):
            data, meta, error = read_geotiff(uploaded_file.read(), uploaded_file.name)
        
        if error:
            st.error(f"Error reading file: {error}")
            return
        
        if data is not None:
            process_and_display(
                data, uploaded_file.name, meta, 
                selected_cmap, auto_range, 
                manual_vmin, manual_vmax, viz_type
            )
    
    elif upload_type == "ZIP Archive" and uploaded_file is not None:
        with st.spinner("Extracting ZIP archive..."):
            tif_files = extract_zip(uploaded_file.read())
        
        if not tif_files:
            st.warning("No GeoTIFF files found in the ZIP archive.")
            return
        
        st.success(f"✅ Found {len(tif_files)} GeoTIFF files")
        
        selected_file = st.selectbox(
            "Select product to view:",
            list(tif_files.keys()),
            format_func=lambda x: f"[{detect_product_type(x).upper()}] {x}"
        )
        
        if selected_file:
            file_info = tif_files[selected_file]
            meta = {'crs': file_info['crs'], 'width': file_info['shape'][1], 'height': file_info['shape'][0]}
            
            process_and_display(
                file_info['data'], selected_file, meta,
                selected_cmap, auto_range,
                manual_vmin, manual_vmax, viz_type
            )
        
        # Comparison view
        st.markdown("---")
        st.markdown("### 📊 Compare Products")
        
        compare_cols = st.columns(2)
        with compare_cols[0]:
            compare1 = st.selectbox("Product 1:", ["None"] + list(tif_files.keys()), key="cmp1")
        with compare_cols[1]:
            compare2 = st.selectbox("Product 2:", ["None"] + list(tif_files.keys()), key="cmp2")
        
        if compare1 != "None" and compare2 != "None":
            col1, col2 = st.columns(2)
            
            with col1:
                data1 = tif_files[compare1]['data']
                pt1 = detect_product_type(compare1)
                cmap1 = get_default_colormap(pt1) if selected_cmap == "auto" else selected_cmap
                vmin1, vmax1 = np.nanpercentile(data1, [2, 98])
                
                fig1 = create_plotly_figure(
                    data1, pt1.upper(),
                    PLOTLY_COLORSCALES.get(cmap1, 'Viridis'),
                    vmin1, vmax1
                )
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                data2 = tif_files[compare2]['data']
                pt2 = detect_product_type(compare2)
                cmap2 = get_default_colormap(pt2) if selected_cmap == "auto" else selected_cmap
                vmin2, vmax2 = np.nanpercentile(data2, [2, 98])
                
                fig2 = create_plotly_figure(
                    data2, pt2.upper(),
                    PLOTLY_COLORSCALES.get(cmap2, 'Viridis'),
                    vmin2, vmax2
                )
                st.plotly_chart(fig2, use_container_width=True)
    
    elif upload_type == "Multiple GeoTIFFs" and uploaded_file:
        st.success(f"✅ Uploaded {len(uploaded_file)} files")
        
        tif_data = {}
        for f in uploaded_file:
            data, meta, error = read_geotiff(f.read(), f.name)
            if data is not None:
                tif_data[f.name] = {'data': data, 'meta': meta}
        
        if tif_data:
            selected_file = st.selectbox(
                "Select product to view:",
                list(tif_data.keys()),
                format_func=lambda x: f"[{detect_product_type(x).upper()}] {x}"
            )
            
            if selected_file:
                file_info = tif_data[selected_file]
                process_and_display(
                    file_info['data'], selected_file, file_info['meta'],
                    selected_cmap, auto_range,
                    manual_vmin, manual_vmax, viz_type
                )
    
    else:
        # No file uploaded
        st.markdown("""
        <div style='text-align: center; padding: 50px;'>
            <h2>👆 Upload InSAR Products to Begin</h2>
            <p style='color: #a0a0a0;'>
                Use the sidebar to upload GeoTIFF files from ASF On-Demand processing.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Sample visualization
        st.markdown("---")
        st.markdown("### 🎯 Sample Visualization")
        
        x = np.linspace(-3, 3, 100)
        y = np.linspace(-3, 3, 100)
        X, Y = np.meshgrid(x, y)
        sample_data = np.sin(np.sqrt(X**2 + Y**2) * 3)
        
        fig = create_plotly_figure(
            sample_data, 
            "Sample Interferogram Pattern",
            "Rainbow",
            -1, 1
        )
        st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()