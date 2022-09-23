#!/usr/bin/env python

"""
Make a Digital Surface Model (DSM) from a digital elevation model
(DEM) (also known as a bare-earth model) by adding building data
from a shapefile.

Shapefile data is proceesed first. Some buildings do not have
height data, and some buildings seem missing altogether. This
is remedied by data imputation and cross-referencing with
buildings fround on OpenStreetMaps.
"""

# load packages
import fiona
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
import osmnx as ox
import rioxarray as rxr
from shapely.geometry import mapping

# plotting
import matplotlib.pyplot as plt
import contextily as cx

# coorinate reference ststems
web = 'epsg:3857'
utm = "EPSG:26918"  # https://epsg.io/26918




"""Load and pre-process inputs"""
print("Loading inputs...")

# load extent for plotting
gpd.io.file.fiona.drvsupport.supported_drivers['KML'] = 'rw'
extent = gpd.read_file('input_data/geneva_extent.kml', driver='KML')

# drop duplicitous 'area' in gdf
extent.drop(extent[extent['Name']!='geneva_larger'].index, inplace=True)
extent.geometry = extent.geometry.envelope
print("\t Loaded extent with CRS: \t" + str(extent.crs))


# load DEM (bare earth) raster
dem = rxr.open_rasterio("input_data/geneva_dem.tif", masked=True).squeeze()
dem = dem.rio.clip(extent.geometry.apply(mapping), extent.crs)  # crop
dem.attrs['long_name'] = 'Elevation (m)'  # rename attribute
print("\t Loaded DEM with CRS: \t" + str(dem.rio.crs))

# plot DEM
fig, ax = plt.subplots(figsize=(12,8), dpi=120)
dem.rio.reproject(web).plot.imshow(ax=ax, cmap='terrain', add_colorbar=True, alpha=1)
cx.add_basemap(ax, source=cx.providers.Stamen.TonerLite, alpha=.1)
cx.add_basemap(ax, source=cx.providers.Stamen.TonerLabels, alpha=.2)
ax.set(title=None)
ax.set_axis_off()
plt.tight_layout()
plt.savefig('figures/dem_thumbnail.png')
plt.close()


# load building shapefiles
blds = gpd.read_file('input_data/ontario_buildings/oc_BuildingFootprints.shp')
blds = blds.to_crs(extent.crs)
# drop building outside extent
blds.drop(blds[~blds.geometry.within(extent.iloc[0].geometry)].index, inplace=True)
print("\t Loaded %d buildings in study extent with CRS %s ." % (blds.shape[0], str(blds.crs)))

# get building height in m
blds['height'] = blds['HEIGHT'] * 0.3048  # convert to m

# get centroid of extent lat / lon
lon = extent.geometry.to_crs(utm).centroid.to_crs("EPSG:4326").x.values[0]
lat = extent.geometry.to_crs(utm).centroid.to_crs("EPSG:4326").y.values[0]

      
# load OSM buildings in a 5km radius
blds2 = ox.geometries.geometries_from_point((lat, lon), {'building': True}, dist=10000)
blds2.reset_index(drop=True, inplace=True)
blds2.drop(blds2[blds2.geometry.type != 'Polygon'].index, inplace=True) # drop non-polygons
      
# filter buildings by extent
blds2['in_extent'] = [extent.contains(blds2.geometry.iloc[i]).values[0] for i in range(blds2.shape[0])]
blds2.drop(blds2[~blds2['in_extent']].index, inplace=True)
print("\t Loaded %d OSM buildings inside extent." % blds2.shape[0])
      
      

      
"""Impute missing building data"""
print("Imputing building data...")
print("\t %d buildings lack height data." % (blds.height == 0).sum())
      
# Compute imputed heights
heights = blds[blds.height > 0].groupby('Prop_Class')['height'].mean().to_dict()
stdevs = blds[blds.height > 0].groupby('Prop_Class')['height'].std().to_dict()
classes = list(heights.keys())

blds['imputed'] = False
imputable = (blds.height==0) & blds['Prop_Class'].isin(classes)
blds.loc[imputable, 'height'] = blds[imputable]['Prop_Class'].map(heights)
blds.loc[imputable, 'std'] = blds[imputable]['Prop_Class'].map(stdevs)
blds.loc[imputable, 'imputed'] = True
print("\t Imputed tax classes; %d buildings lack height data." % (blds.height == 0).sum())

      
# plot building heights (should have modes at typical values)
fig, ax = plt.subplots(figsize=(6, 4))
maxHeight = 30
ax.hist(blds[blds['height'] < maxHeight]['height'], bins=15, color='cornflowerblue')
ax.set_title("Original and imputed building heights (Given height ≤ %d )" % maxHeight)
ax.set_ylabel("buildings")
ax.set_xlabel("height (m)")
plt.tight_layout()
plt.savefig('figures/hist_building_height.png')
plt.close()
      
# identify OSM buildings with no corresponding building in blds
temp = blds2.to_crs(utm).sjoin_nearest(blds.to_crs(utm),
                                       how='left', max_distance=300,
                                       distance_col='dist_to_nearest')
temp.drop(temp[temp['dist_to_nearest'] == 0].index, inplace=True)
print("Added %d buildings from OSM." % temp.shape[0])

# plot OSM buildings and original buildings
original = blds[(blds.height > 0) & ~blds.imputed].to_crs(web)
imputed = blds[(blds.height > 0) & blds.imputed].to_crs(web)
missing = blds[blds.height == 0].to_crs(web)

# make plot
with warnings.catch_warnings():
    warnings.simplefilter(action='ignore', category=DeprecationWarning)
    fig, ax = plt.subplots(figsize=(12,8), dpi=120)
    extent.to_crs(web).plot(ax=ax, alpha=.0)
    cx.add_basemap(ax, source=cx.providers.Stamen.TonerLite)
    original.plot(ax=ax, alpha=1, edgecolor='None',facecolor='k')
    imputed.plot(ax=ax, alpha=1, edgecolor='None', facecolor='b',)
    missing.plot(ax=ax, alpha=1, edgecolor='None', facecolor='red')
    temp.to_crs(web).plot(ax=ax, edgecolor='None', facecolor='magenta')

    # set style
    ax.set(title=None)
    ax.set_axis_off()
    plt.tight_layout()
    plt.savefig('figures/building_footprints.png')
    plt.close()
      

# merge OSM buildings (blds2) with temp
final = gpd.GeoDataFrame(pd.concat((blds, temp[['geometry']]), ignore_index=True))
print("\t Imputing by nearest neighbor...")
# mark new additions as imputed
final.loc[final['imputed'].isna(), 'imputed'] = True
final.loc[final['height'].isna(), 'height'] = 0
      
# split data by height availability
neighbors = final[final.height > 0][['geometry', 'height']].copy()
missings = final[final.height == 0].copy()

# harmonize crs
neighbors = neighbors.to_crs(utm)
missings = missings.to_crs(utm)
      
# get height from nearest neighbor
missings = missings.sjoin_nearest(neighbors)
final.loc[final.height == 0, 'height'] = missings['height_right']
print("\t %d buildings lack height data." % (final.height == 0).sum())
      



"""Make DSM"""
print("Making DSM...")
# harmonize crs
final = final.to_crs(epsg=4269)

# make a DSM (may take a while)
dsm = dem.copy()
for index, bld in final.iterrows():
    clipped = dem.rio.clip([bld.geometry], drop=False)  # drop=False retains shape of dem
    dsm = dsm.where(np.isnan(clipped), clipped.mean() + bld.height)
      
# plot DSM
fig, ax = plt.subplots(figsize=(12,8), dpi=120)
dsm.rio.reproject(web).plot.imshow(ax=ax, cmap='terrain', add_colorbar=True)
cx.add_basemap(ax, source=cx.providers.Stamen.TonerLite, alpha=.1)
cx.add_basemap(ax, source=cx.providers.Stamen.TonerLabels, alpha=.2)
ax.set(title=None)
ax.set_axis_off()
plt.tight_layout()
plt.savefig('figures/dsm_thumbnail.png')
plt.close()
 
print("Saving DSM...")
# save dsm as .tif
dsm.rio.to_raster("geneva_dsm.tif")
print("\t DSM saved. Closing.")