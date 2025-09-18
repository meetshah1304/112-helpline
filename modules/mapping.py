# modules/mapping.py
# Placeholder mapping functions for Sprint-1.
# In Sprint-2 we'll replace / extend these to return Folium maps or GeoJSON.
import pydeck as pdk
import pandas as pd

def create_point_geojson(df, lat_col="caller_lat", lon_col="caller_lon", properties=None):
    """
    Create a simple GeoJSON FeatureCollection (dict) of points.
    properties: list of columns to include as properties for each feature
    """
    features = []
    if properties is None:
        properties = []

    for _, row in df.iterrows():
        lat = row.get(lat_col)
        lon = row.get(lon_col)
        if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
            continue
        props = {p: (row.get(p) if p in row else None) for p in properties}
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "properties": props
        }
        features.append(feature)
    return {"type": "FeatureCollection", "features": features}


def clean_df_for_pydeck(df, lat_col="caller_lat", lon_col="caller_lon"):
    """Ensure DataFrame is JSON-serializable for Pydeck."""
    df = df[[lat_col, lon_col, "category", "jurisdiction"]].dropna().copy()

    # Force to float for coords
    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce").astype(float)
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce").astype(float)

    # Ensure no NaNs
    df = df.dropna(subset=[lat_col, lon_col])

    # Convert other fields to string (for tooltip safety)
    df["category"] = df["category"].astype(str)
    df["jurisdiction"] = df["jurisdiction"].astype(str)

    df["weight"] = 1.0  # for heatmap intensity

    return df

def pydeck_points_map(df, lat_col="caller_lat", lon_col="caller_lon"):
    df = clean_df_for_pydeck(df, lat_col, lon_col)
    if df.empty:
        return None

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=[lon_col, lat_col],
        get_color=[0, 100, 255, 160],
        get_radius=80,
        pickable=True,
    )

    view_state = pdk.ViewState(
        latitude=df[lat_col].mean(),
        longitude=df[lon_col].mean(),
        zoom=9,
        pitch=0,
    )

    return pdk.Deck(layers=[layer], initial_view_state=view_state,
                    tooltip={"text": "{category}, {jurisdiction}"})

def pydeck_heatmap(df, lat_col="caller_lat", lon_col="caller_lon"):
    df = clean_df_for_pydeck(df, lat_col, lon_col)
    if df.empty:
        return None

    COLOR_RANGE = [
        [0, 0, 255, 25],    # blue
        [0, 255, 255, 85],  # cyan
        [0, 255, 0, 170],   # green
        [255, 255, 0, 200], # yellow
        [255, 0, 0, 255],   # red
    ]

    layer = pdk.Layer(
        "HeatmapLayer",
        data=df,
        get_position=[lon_col, lat_col],
        get_weight="weight",
        radiusPixels=40,   # reduce radius so clusters form
        intensity=2,
        threshold=0.05,     # filter very low density
        color_range = COLOR_RANGE
    )

    view_state = pdk.ViewState(
        latitude=df[lat_col].mean(),
        longitude=df[lon_col].mean(),
        zoom=9,
        pitch=0,
    )

    return pdk.Deck(layers=[layer], initial_view_state=view_state)

def pydeck_hexbin_map(df, lat_col="caller_lat", lon_col="caller_lon", color_by_category=False):
    """Create 3D hexagonal hotspot visualization using PyDeck HexagonLayer."""
    
    # Clean and prepare data
    df_clean = df.copy()
    
    # Ensure we have the required columns and they're numeric
    if lat_col not in df_clean.columns or lon_col not in df_clean.columns:
        print(f"Missing required columns: {lat_col}, {lon_col}")
        return None
    
    # Convert to numeric and drop invalid coordinates
    df_clean[lat_col] = pd.to_numeric(df_clean[lat_col], errors='coerce')
    df_clean[lon_col] = pd.to_numeric(df_clean[lon_col], errors='coerce')
    df_clean = df_clean.dropna(subset=[lat_col, lon_col])
    
    if df_clean.empty:
        print("No valid coordinates found for hexbin mapping")
        return None
    
    # Filter for realistic Goa coordinates (approximate bounds)
    # Goa latitude: ~14.9-15.8, longitude: ~73.7-74.3
    goa_bounds = {
        'lat_min': 14.5, 'lat_max': 16.0,
        'lon_min': 73.0, 'lon_max': 75.0
    }
    
    df_clean = df_clean[
        (df_clean[lat_col] >= goa_bounds['lat_min']) & 
        (df_clean[lat_col] <= goa_bounds['lat_max']) &
        (df_clean[lon_col] >= goa_bounds['lon_min']) & 
        (df_clean[lon_col] <= goa_bounds['lon_max'])
    ]
    
    if df_clean.empty:
        print("No coordinates within Goa bounds")
        return None
    
    # Prepare data for HexagonLayer - ensure all data is JSON-serializable
    df_clean = df_clean.copy()
    
    # Convert all numeric columns to native Python types
    df_clean[lat_col] = df_clean[lat_col].astype(float).tolist()
    df_clean[lon_col] = df_clean[lon_col].astype(float).tolist()
    
    # Create position array with native Python floats
    positions = []
    for _, row in df_clean.iterrows():
        positions.append([float(row[lon_col]), float(row[lat_col])])
    
    # Create a clean dataset with only necessary columns
    clean_data = []
    for i, (_, row) in enumerate(df_clean.iterrows()):
        record = {
            'position': positions[i],
            'category': str(row.get('category', 'unknown')) if 'category' in df_clean.columns else 'unknown',
            'jurisdiction': str(row.get('jurisdiction', 'unknown')) if 'jurisdiction' in df_clean.columns else 'unknown'
        }
        clean_data.append(record)
    
    # Create category color mapping for potential future use
    category_colors = {
        'crime': [255, 50, 50, 200],      # Red
        'medical': [50, 255, 50, 200],    # Green  
        'accident': [255, 255, 50, 200],  # Yellow
        'women_safety': [255, 50, 255, 200], # Magenta
        'other': [50, 150, 255, 200]      # Blue
    }
    
    # Default color for hexagons
    default_color = [255, 140, 0, 180]  # Orange
    
    # Calculate center point for view (using original df_clean before conversion)
    center_lat = float(pd.to_numeric(df[lat_col], errors='coerce').mean())
    center_lon = float(pd.to_numeric(df[lon_col], errors='coerce').mean())
    
    # Decide which layers to create
    if color_by_category and 'category' in df_clean.columns:
        # Create category-specific layers
        deck_layers = []
        categories = set(record['category'] for record in clean_data)
        
        for category in categories:
            # Filter data for this category
            cat_data = [record for record in clean_data if record['category'] == category]
            if not cat_data:
                continue
                
            # Get color for this category
            color = list(category_colors.get(category, default_color))
            
            # Create layer for this category
            cat_layer = pdk.Layer(
                'HexagonLayer',
                data=cat_data,
                get_position='position',
                radius=400,  # Slightly smaller for multiple layers
                elevation_scale=80,
                elevation_range=[0, 800],
                extruded=True,
                coverage=0.8,
                get_elevation_weight=1,
                get_color_weight=1,
                color_range=[
                    [color[0], color[1], color[2], 100],
                    [color[0], color[1], color[2], 150],
                    [color[0], color[1], color[2], 200],
                ],
                pickable=True,
                auto_highlight=True
            )
            deck_layers.append(cat_layer)
            
    else:
        # Create single layer with density-based coloring
        hexagon_layer = pdk.Layer(
            'HexagonLayer',
            data=clean_data,
            get_position='position',
            radius=500,  # Radius in meters - adjust based on zoom level
            elevation_scale=100,  # Scale factor for height
            elevation_range=[0, 1000],  # Min/max height in meters
            extruded=True,  # Enable 3D extrusion
            coverage=0.9,  # Coverage of hexagon (0-1)
            get_elevation_weight=1,  # Weight for each data point
            get_color_weight=1,  # Weight for color calculation
            color_range=[
                [255, 255, 204, 100],  # Light yellow (low density)
                [255, 237, 160, 120],  # Light orange
                [254, 217, 118, 140],  # Orange
                [254, 178, 76, 160],   # Dark orange
                [253, 141, 60, 180],   # Red-orange
                [240, 59, 32, 200],    # Red (high density)
            ],
            pickable=True,
            auto_highlight=True
        )
        deck_layers = [hexagon_layer]
    
    # Set up the view state
    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=10,  # Adjust zoom level for Goa
        min_zoom=8,
        max_zoom=15,
        pitch=45,  # 3D angle
        bearing=0,  # Rotation
        height=600,
        width=800
    )
    
    # Create tooltip
    tooltip = {
        "html": """
        <b>Call Density Hotspot</b><br/>
        <b>Calls:</b> {elevationValue}<br/>
        <b>Coordinates:</b> {position}
        """,
        "style": {
            "backgroundColor": "steelblue",
            "color": "white",
            "fontSize": "12px",
            "padding": "8px",
            "borderRadius": "4px"
        }
    }
    
    # Create the deck
    deck = pdk.Deck(
        layers=deck_layers,
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style='mapbox://styles/mapbox/light-v9'  # Clean base map
    )
    
    print(f"Created hexbin map with {len(clean_data)} data points")
    print(f"Center: {center_lat:.4f}, {center_lon:.4f}")
    
    return deck

# --- Wrapper functions for app.py compatibility ---
def plot_points_on_map(df):
    """Wrapper for pydeck_points_map for backward compatibility."""
    return pydeck_points_map(df)

def plot_heatmap(df):
    """Wrapper for pydeck_heatmap for backward compatibility."""
    return pydeck_heatmap(df)