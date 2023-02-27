import glob
import logging
import os
from pathlib import Path
import shutil
import zipfile

import geopandas
import numpy as np
from osgeo import gdal
import rasterio as rio
from rasterio.merge import merge
from sentinelsat import geojson_to_wkt, read_geojson, SentinelAPI


logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

AOI_SHAPEFILE = Path('./data/aoi/shp/Visakhapatnam_Simplified_Polygon.shp')
AOI_GEOJSON = Path('./data/aoi/Visakhapatnam_Simplified_Polygon.geojson')
COPERNICUS_USERNAME = ''
COPERNICUS_PASSWORD = os.environ.get('COPERNICUS_PASSWORD', '')
PATH_SENTINEL_IMAGERY = Path('./data/sentinel')
PATH_BANDS = Path('./data/bands')
PATH_OUTPUT = Path('./output')


def download_sentinel_imagery():
    """
    Downloads the requested Sentinel imagery from Copernicus.
    This function converts the given shapefile to GeoJSON and uses it as the area of interest.
    A shapefile with simplified polygon shall be provided as the input.
    """

    logging.info('Converting shapefile to GeoJSON')
    shp_file = geopandas.read_file(AOI_SHAPEFILE)
    shp_file.to_file(AOI_GEOJSON, driver='GeoJSON')

    logging.info('Creating directory to store Sentinel imagery')
    PATH_SENTINEL_IMAGERY.mkdir()

    api = SentinelAPI(COPERNICUS_USERNAME, COPERNICUS_PASSWORD)
    area_of_interest = geojson_to_wkt(read_geojson(AOI_GEOJSON))
    products = api.query(area_of_interest,
                         date=('NOW-10DAYS', 'NOW'),
                         platformname='Sentinel-2',
                         producttype='S2MSI2A',
                         cloudcoverpercentage=(0, 5))
    api.download_all(list(products.keys()), str(PATH_SENTINEL_IMAGERY))


def extract_imagery():
    zipped_files = PATH_SENTINEL_IMAGERY.glob('*.zip')
    for _ in zipped_files:
        logging.info('Extracting zipfile: ' + str(_))
        with zipfile.ZipFile(_, 'r') as zipped_file:
            zipped_file.extractall(str(PATH_SENTINEL_IMAGERY))


def collect_band_for_resolution(resolution, band):
    logging.info('Collecting band ' + band)
    Path(PATH_BANDS/band).mkdir(parents=True, exist_ok=True)
    data = glob.glob(str(PATH_SENTINEL_IMAGERY)+'/**/'+resolution+'/*'+band+'.jp2', recursive=True)
    for _ in data:
        shutil.copy(_, str(PATH_BANDS/band))


def mosaic_imagery(band):
    """
    Reference: URL
    """
    files_for_band = list((PATH_BANDS/band).iterdir())
    files_to_mosaic = []
    for _ in files_for_band:
        raster = rio.open(_)
        files_to_mosaic.append(raster)

    mosaic, output = merge(files_to_mosaic)
    metadata = raster.meta.copy()
    metadata.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": output
    })
    with rio.open(str(PATH_BANDS/band/'mosaic.tiff'), 'w', **metadata) as _:
        _.write(mosaic)


def generate_ndvi(red_band, nir_band):
    """

    """
    band_4 = rio.open(str(PATH_BANDS/red_band/'clipped.tiff'))
    band_8 = rio.open(str(PATH_BANDS/nir_band/'clipped.tiff'))
    red = band_4.read()
    nir = band_8.read()
    np.seterr(divide='ignore', invalid='ignore')

    ndvi = (nir.astype(float) - red.astype(float)) / (nir + red)

    metadata = band_4.meta
    metadata.update(driver='GTiff')
    metadata.update(dtype=rio.float32)

    with rio.open(str(PATH_OUTPUT/'NDVI_{}_{}.tiff'.format(red_band, nir_band)), 'w', **metadata) as _:
        _.write(ndvi.astype(rio.float32))


if __name__ == '__main__':
    download_sentinel_imagery()

    # Pre-process imagery
    extract_imagery()
    for resolution, band in [('R10m', 'B04_10m'), ('R10m', 'B08_10m'), ('R20m', 'B04_20m'), ('R20m', 'B8A_20m')]:
        collect_band_for_resolution(resolution, band)
    for band in ['B04_10m', 'B08_10m', 'B04_20m', 'B8A_20m']:
        logging.info('Mosaic-ing band ' + band)
        mosaic_imagery(band)
        logging.info('Clipping band {} to area of interest'.format(band))
        gdal.Warp(str(PATH_BANDS/band/'clipped.tiff'),
                  str(PATH_BANDS/band/'mosaic.tiff'),
                  cutlineDSName=Path('shp/Visakhapatnam.shp'),
                  cropToCutline=True,
                  dstNodata=0)

    logging.info('Generating NDVI')
    generate_ndvi('B04_10m', 'B08_10m')
    generate_ndvi('B04_20m', 'B8A_20m')
