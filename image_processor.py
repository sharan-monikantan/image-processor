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
COPERNICUS_USERNAME = os.environ.get('COPERNICUS_USERNAME', '')
COPERNICUS_PASSWORD = os.environ.get('COPERNICUS_PASSWORD', '')
PATH_SENTINEL_IMAGERY = Path('./data/sentinel')
PATH_BANDS = Path('./data/bands')
PATH_OUTPUT = Path('./output')


def download_sentinel_imagery():
    """
    Downloads the requested Sentinel imagery from Copernicus Open Access Hub.

    :return: None
    """

    # Shapefile is converted to GeoJSON as the API supports GeoJSON format.
    logging.info('Converting shapefile to GeoJSON')
    shp_file = geopandas.read_file(AOI_SHAPEFILE)
    shp_file.to_file(AOI_GEOJSON, driver='GeoJSON')

    logging.info('Creating directory to store Sentinel imagery')
    if PATH_SENTINEL_IMAGERY.exists():
        shutil.rmtree(PATH_SENTINEL_IMAGERY)
    PATH_SENTINEL_IMAGERY.mkdir()

    api = SentinelAPI(COPERNICUS_USERNAME, COPERNICUS_PASSWORD)
    area_of_interest = geojson_to_wkt(read_geojson(AOI_GEOJSON))
    products = api.query(area_of_interest,
                         date=('NOW-10DAYS', 'NOW'),
                         platformname='Sentinel-2',
                         producttype='S2MSI2A',
                         cloudcoverpercentage=(0, 5))
    api.download_all(list(products.keys()), str(PATH_SENTINEL_IMAGERY))


def extract_imagery_from_zip():
    """
    Extracts Sentinel imagery from the downloaded zip files

    :return: None
    """
    zipped_files = PATH_SENTINEL_IMAGERY.glob('*.zip')
    for _ in zipped_files:
        logging.info('Extracting zipfile: ' + str(_))
        with zipfile.ZipFile(_, 'r') as zipped_file:
            zipped_file.extractall(str(PATH_SENTINEL_IMAGERY))


def collect_imagery_for_band(band):
    """
    Collects all imagery of a specific band/resolution, e.g., B04_10m.
    The collected imagery will be used for subsequent processing.

    :param str band: The band to collect.
    :return: None
    """
    logging.info('Collecting band ' + band)
    Path(PATH_BANDS/band).mkdir(parents=True, exist_ok=True)
    data = glob.glob(str(PATH_SENTINEL_IMAGERY)+'/**/*'+band+'.jp2', recursive=True)
    for _ in data:
        shutil.copy(_, str(PATH_BANDS/band))


def mosaic_imagery_for_aoi(band):
    """
    Mosaics all imagery of a specific band.

    :param str band: The band for which all imagery is to be mosaic-ed.
    :return: None
    """
    imagery_for_band = list((PATH_BANDS/band).iterdir())
    imagery_to_mosaic = []
    for _ in imagery_for_band:
        imagery = rio.open(_)
        imagery_to_mosaic.append(imagery)

    mosaic, transform = merge(imagery_to_mosaic)
    metadata = imagery.meta.copy()
    metadata.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": transform
    })
    with rio.open(str(PATH_BANDS/band/'mosaic.tiff'), 'w', **metadata) as _:
        _.write(mosaic)


def generate_ndvi(red_band, nir_band):
    """
    Creates NDVI imagery using the input Red and NIR bands.

    :param str red_band: The Red band to use. e.g., B04_10m
    :param str nir_band: The NIR band to use. e.g., B08_10m
    :return: None
    """
    logging.info('Generating NDVI using {}, {}'.format(red_band, nir_band))
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

    # Pre-processing imagery
    extract_imagery_from_zip()
    bands = ['B04_10m', 'B08_10m', 'B04_20m', 'B8A_20m']

    if PATH_BANDS.exists():
        shutil.rmtree(PATH_BANDS)
    for band in bands:
        collect_imagery_for_band(band)

    for band in bands:
        logging.info('Mosaicing imagery for band ' + band)
        mosaic_imagery_for_aoi(band)
        logging.info('Clipping band {} to area of interest'.format(band))
        gdal.Warp(str(PATH_BANDS/band/'clipped.tiff'),
                  str(PATH_BANDS/band/'mosaic.tiff'),
                  cutlineDSName=Path('./data/aoi/shp/Visakhapatnam.shp'),
                  cropToCutline=True,
                  dstNodata=0)

    # Generating NDVI for 10m and 20m resolutions
    if PATH_OUTPUT.exists():
        shutil.rmtree(PATH_OUTPUT)
    PATH_OUTPUT.mkdir()
    generate_ndvi('B04_10m', 'B08_10m')
    generate_ndvi('B04_20m', 'B8A_20m')
