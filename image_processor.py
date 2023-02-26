import logging
from pathlib import Path
import zipfile

import geopandas
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


if __name__ == '__main__':
    download_sentinel_imagery()

    # Pre-process imagery
    extract_imagery()
