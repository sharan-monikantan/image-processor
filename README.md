# Image Processor
*Python module to generate NDVI from Sentinel imagery*

The Python module downloads Sentinel imagery for an area of interest (AOI) from Copernicus Open Access Hub, 
processes the imagery and generates NDVI images for the AOI.

The AOI used is the district of Visakhapatnam, Andra Pradesh. Shapefile for the AOI is obtained from
https://github.com/HindustanTimesLabs/shapefiles. A simplified version of the shapefile, generated using ArcGIS Pro,
is used to query Copernicus Open Access Hub, as the platform has a limit for the number of vertices the AOI shapefile can have.

## Setting up

### Installing dependencies
The requirements.txt file has the list of Python packages required to run the module. The required packages can be
installed using the following command:

```commandline
conda install --channel conda-forge --yes --file requirements.txt
```

### Copernicus Open Access Hub credentials
In `image_processor.py`, set values for `COPERNICUS_USERNAME` and `COPERNICUS_PASSWORD`.
