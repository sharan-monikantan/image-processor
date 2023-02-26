import glob
import logging
from pathlib import Path
import shutil
import zipfile

import geopandas
import rasterio as rio
from rasterio.merge import merge
from sentinelsat import geojson_to_wkt, read_geojson, SentinelAPI


logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

AOI_SHAPEFILE = Path('./shp/Visakhapatnam_Simplified.shp')
AOI_GEOJSON = Path('./geojson/Visakhapatnam_Simplified.geojson')
COPERNICUS_USERNAME = ''
COPERNICUS_PASSWORD = ''


def download_sentinel_imagery():
    """
    Downloads the requested Sentinel imagery from Copernicus.
    This function converts the given shapefile to GeoJSON and uses it as the area of interest.
    A shapefile with simplified polygon shall be provided as the input.
    """

    logging.info('Converting shapefile to GeoJSON')
    shp_file = geopandas.read_file(AOI_SHAPEFILE)
    shp_file.to_file(AOI_GEOJSON, driver='GeoJSON')

    api = SentinelAPI(COPERNICUS_USERNAME, COPERNICUS_PASSWORD)
    area_of_interest = geojson_to_wkt(read_geojson(AOI_GEOJSON))
    products = api.query(area_of_interest,
                         date=('NOW-9DAYS', 'NOW'),
                         platformname='Sentinel-2',
                         producttype='S2MSI2A',
                         cloudcoverpercentage=(0, 5))
    api.download_all(list(products.keys()), './sentinel_imagery')


def extract_imagery():
    zipped_files = Path('./sentinel_imagery').glob('*.zip')
    for _ in zipped_files:
        logging.info('Extracting file: ' + str(_))
        with zipfile.ZipFile(_, 'r') as zipped_file:
            zipped_file.extractall('./sentinel_imagery')


def collect_band_for_resolution(resolution, band):
    logging.info('Collecting band ' + band)
    Path('./sentinel_imagery/'+band).mkdir(parents=True, exist_ok=True)
    data = glob.glob('./sentinel_imagery/**/'+resolution+'/*'+band+'.jp2', recursive=True)
    for _ in data:
        shutil.copy(_, './sentinel_imagery/'+band)


def mosaic_imagery(band):
    """
    Reference: URL
    """
    files_for_band = list(Path('./sentinel_imagery/'+band).iterdir())
    files_to_mosaic = []
    for _ in files_for_band:
        raster = rio.open(_)
        files_to_mosaic.append(raster)

    mosaic, output = merge(files_to_mosaic)
    output_metadata = raster.meta.copy()
    output_metadata.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": output
    })
    with rio.open('./sentinel_imagery/'+band+'/mosaic.tiff', "w", **output_metadata) as _:
        print(output_metadata)
        _.write(mosaic)


if __name__ == '__main__':
    download_sentinel_imagery()

    # Pre-process imagery
    extract_imagery()
    for resolution, band in [('R10m', 'B04_10m'), ('R10m', 'B08_10m'), ('R20m', 'B04_20m'), ('R20m', 'B8A_20m')]:
        collect_band_for_resolution(resolution, band)
    for band in ['B04_10m', 'B08_10m', 'B04_20m', 'B8A_20m']:
        logging.info('Mosaic-ing band ' + band)
        mosaic_imagery(band)
