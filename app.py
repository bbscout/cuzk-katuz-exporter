### IMPORT LIBRARIES ###
import pandas as pd
import geopandas as gpd
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import pyproj
import streamlit as st
from streamlit_folium import folium_static
import folium
from folium.plugins import Fullscreen
import io

### FUNCTION DEFINITIONS ###

# Download the Directory of Municipalities (DoM)
@st.cache_data # Cache the data to avoid reruning the download
def list_katuz():
    # Read the zipped DoM file using Geopandas
    kat_uz_list = gpd.read_file("zip+https://www.cuzk.cz/CUZK/media/CiselnikyISKN/SC_SEZNAMKUKRA_DOTAZ/SC_SEZNAMKUKRA_DOTAZ.zip?ext=.zip",encoding='cp1250')

    # Add field to dataframe with formated to "Municipality name (municipality code)"
    kat_uz_list['SELECTION_NAME'] = kat_uz_list['OBEC_NAZEV'] + " (" + kat_uz_list['OBEC_KOD'] + ")"

    return kat_uz_list

# Download the Directory of DRUPOZ (type of land)
@st.cache_data # Cache the data to avoid reruning the download
def get_drupoz_directory():
    # Read the zipped DRUPOZ directory file using Geopandas
    drupoz = gpd.read_file(f"zip+https://cuzk.cz/CUZK/media/CiselnikyISKN/SC_D_POZEMKU/SC_D_POZEMKU.zip",encoding='cp1250').drop(columns='geometry')

    # Use only necessary columns - code, name, abbreviation
    drupoz = drupoz[['KOD','NAZEV','ZKRATKA']]

    # Change the code column to type integr
    drupoz['KOD'] = drupoz['KOD'].astype(str).astype(int)

    # Rename the columns
    drupoz = drupoz.rename(columns={"KOD": "DRUPOZ_KOD", "NAZEV": "DRUPOZ_NAZEV", "ZKRATKA": "DRUPOZ_ZKRATKA"})

    return drupoz

# Download the Directory of ZPVYPA (type of landuse)
@st.cache_data # Cache the data to avoid reruning the download
def get_zpvyuz_directory():
    # Read the zipped ZPVYPA directory file using Geopandas
    zpvyuz = gpd.read_file(f"zip+https://cuzk.cz/CUZK/media/CiselnikyISKN/SC_ZP_VYUZITI_POZ/SC_ZP_VYUZITI_POZ.zip",encoding='cp1250').drop(columns='geometry')

    # Use only necessary columns - code, name, abbreviation
    zpvyuz = zpvyuz[['KOD','NAZEV','ZKRATKA']]

    # Change the code column to type integr
    zpvyuz['KOD'] = zpvyuz['KOD'].astype(str).astype(int)

    # Rename the columns
    zpvyuz = zpvyuz.rename(columns={"KOD": "ZPVYPA_KOD", "NAZEV": "ZPVYPA_NAZEV", "ZKRATKA": "ZPVYPA_ZKRATKA"})

    return zpvyuz

# Download and merge data into one dataframe
@st.cache_data # Cache the data to avoid reruning the download of same cadastral units
def get_n_merge_kn(cislo_ku):
    # Download shapefile with cadastral parcels for specified cadastral unit
    kn = gpd.read_file(f"zip+https://services.cuzk.cz/shp/ku/epsg-5514/{cislo_ku}.zip!{cislo_ku}/PARCELY_KN_P.shp")

    # Download shapefile with defpoints (details for each land parcel)
    defpoints = gpd.read_file(f"zip+https://services.cuzk.cz/shp/ku/epsg-5514/{cislo_ku}.zip!{cislo_ku}/PARCELY_KN_DEF.shp")

    # Remove the geometry column ()
    deftable = defpoints.drop(columns='geometry')

    # Merge parcel data with its defpoints based on ID_2 column (unique for each land parcel)
    kn_merge = kn.merge(deftable, on='ID_2')

    # Get the dataframe with coded values of DRUPOZ
    drupoz = get_drupoz_directory()

    # Merge the coded values with named DRUPOZ categories
    kn_merge_drupoz = kn_merge.merge(drupoz, on='DRUPOZ_KOD')

    # Get the dataframe with coded values od ZPVYPA
    zpvyuz = get_zpvyuz_directory()

    # Merge the coded values with named ZPVYPA categories
    kn_merge_all = kn_merge_drupoz.merge(zpvyuz, on='ZPVYPA_KOD',how='left')
    return kn_merge_all

### WEBSITE HEADER ###

# Heading
st.title('Export a zobrazení dat katastrálních území')

# Description of the website
'''Aplikace stahuje data přímo z ČÚZK (https://services.cuzk.cz/shp/ku) s týdenní aktualizací. Stažení a zpracování dat chvilku trvá.'''


### SECTION 1 - Select municipalities and cadastral units ###

# Subheading
st.subheader('Seznam katastrálních území')

# Get list of cadastral units from ČUZK
kat_uz_list = list_katuz()

# Two column layout for select inputs
col1, col2 = st.columns(2)

# Create a multiselect widget for selecting municipalities
selected_municipalities = col1.multiselect(
    "Vyberte jednu nebo více obcí",
    sorted(kat_uz_list["SELECTION_NAME"].unique()),
    help = "Zadejte název nebo číslo obce")

# Filter the DataFrame to show only the rows corresponding to the selected municipalities
filtered_data = kat_uz_list[kat_uz_list["SELECTION_NAME"].isin(selected_municipalities)]

# Create a multiselect widget for selecting cadastral units within the selected municipalities
selected_cadastral_units = col2.multiselect(
    "Vyber jedno nebo více katastrálních území",
    filtered_data["KU_NAZEV"].unique())

### SECTION 2

options = {"Obrysy parcel":"OBEC_KOD", "Druh pozemku":"DRUPOZ_NAZEV", "Způsob využití pozemku":"ZPVYPA_NAZEV"}

sel_option = st.radio("Zobrazit", options.keys(), horizontal=True)

# filter the DataFrame to show only the rows corresponding to the selected cadastral units
filtered_data = filtered_data[filtered_data["KU_NAZEV"].isin(selected_cadastral_units)]


cisla_ku = list(filtered_data["KU_KOD"])

gpd_kn_list = []
if len(cisla_ku) > 5:
   st.warning('Nepřeháněj to, nebo mi zavaříš komp...', icon="⚠️")
if len(cisla_ku) > 0:
     
    #progressbar
    step = 1 / len(cisla_ku)
    percent_complete = 0
    progress_text = "Stahuji data jednotlivých katastrů z ČÚZK..."
    my_bar = st.progress(percent_complete, text=progress_text)

    for cislo_ku in cisla_ku:
        gpd_kn = get_n_merge_kn(cislo_ku)
        gpd_kn_list.append(gpd_kn)

        #update progressbar
        percent_complete += step
        my_bar.progress(percent_complete, text=progress_text)

    kn_merge_all = gpd.GeoDataFrame(pd.concat(gpd_kn_list, ignore_index=True))     
    kn_proj = kn_merge_all.to_crs(pyproj.CRS.from_epsg(4326))

    with st.spinner('Kreslím mapu...'):
        
        # Define a colormap based on the unique categories in the "DRUPOZ_NAZEV" column
        kn_proj['ZPVYPA_NAZEV'].fillna('bez uvedení',inplace=True)

        categories = kn_proj[options[sel_option]].unique()
        cmap = plt.get_cmap('tab20', len(categories))
        colors = [mcolors.rgb2hex(cmap(i)) for i in range(len(categories))]

        # Create a map using Folium
        m = folium.Map(location=[kn_proj.geometry.centroid.y.mean(), kn_proj.geometry.centroid.x.mean()], zoomSnap=0.1)
    
        for i, category in enumerate(categories):
            color = colors[i]
            group = folium.FeatureGroup(name=f"<span style='color:{color};'>⬤</span> {category}")
            kn_proj_category = kn_proj[kn_proj[options[sel_option]] == category]

            # Add the polygons to the map, colored by category
            for _, row in kn_proj_category.iterrows():
                folium.GeoJson(row.geometry.__geo_interface__, style_function=lambda x, color=color: {'fillColor': color, 'fillOpacity': 0.5, 'opacity': 0.2, 'color': 'black', 'weight': 1},tooltip=row["TEXT_KM"]).add_to(group)
            group.add_to(m)

        if options[sel_option] != "OBEC_KOD":
            # Add a layer control to the map
            folium.LayerControl().add_to(m)        
        
        #Add fullscreen option to the map
        Fullscreen().add_to(m)
        
        #Fit map bounds
        m.fit_bounds(m.get_bounds())
        
        st.subheader('Katastrální mapa vybraných území')

        # call to render Folium map in Streamlit
        folium_static(m)

        my_bar.empty()

        with st.expander("Zobrazit tabulkový přehled"):
            kn_merge_all['ODKAZ_NAHLIZENI'] = 'https://nahlizenidokn.cuzk.cz/ZobrazObjekt.aspx?typ=Parcela&id=' + kn_merge_all['ID_2'] 
            st.dataframe(kn_merge_all.drop(columns=['ID_x','KATUZE_KOD_x','TYPPPD_KOD_x','ID_y','TYPPPD_KOD_y','DRUPOZ_KOD','ZPVYPA_KOD','DRUPOZ_ZKRATKA','ZPVYPA_ZKRATKA','STAV_PARC','geometry']))

        st.subheader('Stáhnout data')
        
        #Layout tlačítek
        col3, col4 = st.columns(2)

        #"Shapefile":{"name":"Shapefile", "ext":".shp", "driver":"ESRI Shapefile"},
        export_options = {"CSV":{"name":"CSV", "ext":".csv", "driver":None, "mime": "text/csv"}, "GeoJSON": {"name":"GeoJSON", "ext":".geojson", "driver":"GeoJSON", "mime": "application/geo+json"}, "GeoPackage":{"name":"GeoPackage", "ext":".gpkg", "driver":"GPKG", "mime": "application/x-sqlite3"}}
        export_sel_option = col3.radio("Formát", export_options.keys(), horizontal=True)
        
        crs_options = {"S-JTSK":5514,"WGS 84":4326}
        crs_sel_option = col4.radio("Souřadnicový systém", crs_options.keys(), horizontal=True)

        @st.cache_data
        def export_file(_gdf, exp_type, crs):
            # IMPORTANT: Cache the conversion to prevent computation on every rerun
            if exp_type['name'] == 'CSV':
                file = _gdf.to_csv(encoding='utf-8')
            else:
                file = io.BytesIO()
                _gdf.to_crs(pyproj.CRS.from_epsg(crs)).to_file(file,encoding='utf-8',crs=crs, driver=exp_type['driver'])

            return file
        
        file = export_file(kn_merge_all, export_options[export_sel_option], crs_options[crs_sel_option])

        st.download_button(
            label="Stáhnout " + export_options[export_sel_option]['name'],
            data=file,
            file_name='parcely_kn' + export_options[export_sel_option]['ext'],
            mime=export_options[export_sel_option]['ext'],
        )