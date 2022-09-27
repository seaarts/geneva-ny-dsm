# geneva-ny-dsm
A synthetic Digital Surface Model raster for Geneva, NY


Based on data avialble at the [Ontario County GIS Data Resource Center](https://ontariocountyny.gov/1156/Ontario-County-GIS-Data-Resource-Center).

This project provides a synthetic Digital Surface Model (DSM) raster for an area around Geneva, NY. Code for generating the data is also available in `make_dsm.py`. A DSM is a model of surface elevation, inlcuding man-made structures such as buildings. In the United States the [3D elevation program](https://www.usgs.gov/3d-elevation-program) contains comprehensive [LiDAR](https://en.wikipedia.org/wiki/Lidar) point cloud coverage, from which accurate DSMs can be derived, however there are areas, particularly rural ones, for which no coverage exists. Ready-to-use DSMs are only available for select areas. However most of the United States has Digital Elevation Model (DEM) data available; this only describes the bare-earth. 

In this simple project we generate a synthetic DSM by merging a DEM, building footprints, and building height data. The result is a raster (`geneva_dsm.tif`).
