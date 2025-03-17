import azure.functions as func
import logging
import osgeo
from osgeo import gdal
from affine import Affine
import os
import struct
import json
from ci import confidence_interval_values

# For testing only, set connection string in app settings so it can be updated when storage keys are rotated
# TODO: set app settings for access to S3?
#os.environ["AZURE_STORAGE_CONNECTION_STRING"] = f""

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
gdal.osr.UseExceptions()

@app.route(route="get_values", methods=["POST"])
def http_trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # Make sure we have all expected input parameters and that they are valid
    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            "Please pass a JSON object with {'file' (string), 'bands' (int array), 'lat' (float), 'lon' (float)} fields in the request body",
            status_code=400
        )
    else:
        file = req_body.get('file')
        bands = req_body.get('bands')
        lat = req_body.get('lat')
        lon = req_body.get('lon')

    if not file or not isinstance(file, str):
        return func.HttpResponse(f"Please pass a file name in the request body", status_code=400)

    if not bands or not isinstance(bands, list):
        return func.HttpResponse(f"Please pass an array containing at least one band in the request body", status_code=400)
    
    if not lat or not (isinstance(lat, float) or isinstance(lat, int)) or not -90 <= lat <= 90:
        return func.HttpResponse(f"Please pass a valid latitude in the request body", status_code=400)
    
    if not lon or not (isinstance(lon, float) or isinstance(lon, int)) or not -180 <= lon <= 180:
        return func.HttpResponse(f"Please pass a valid longitude in the request body", status_code=400)
    
    # Make sure the file exists
    try:
        # TODO: Update this to point to S3 instead?
        stg = f"/vsiaz/data/{file}"
        ds = gdal.Open(stg, gdal.GA_ReadOnly)
    except:
        return func.HttpResponse(f"File {file} cannot be opened or does not exist", status_code=400)
    
    # make sure the bands specified in the parameters actually exist in the file
    for b in bands:
        if b < 1 or b > ds.RasterCount:
            return func.HttpResponse(f"Band {b} does not exist in the raster", status_code=400)
    
    # set up a transform to convert between lat/lon and whatever the projection of the file is   
    tgtRef = gdal.osr.SpatialReference()
    tgtRef.ImportFromWkt(ds.GetProjection())
    srcRef = gdal.osr.SpatialReference()
    srcRef.ImportFromEPSG(4326)
    if int(osgeo.__version__[0]) >= 3:
        # GDAL 3 changes axis order: https://github.com/OSGeo/gdal/issues/1546
        srcRef.SetAxisMappingStrategy(osgeo.osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = gdal.osr.CoordinateTransformation(srcRef, tgtRef)
    xgeo,ygeo,zgeo = transform.TransformPoint(lon, lat)

    # get the pixel coordinates of the transformed point
    forward_transform = Affine.from_gdal(*ds.GetGeoTransform())
    reverse_transform = ~forward_transform
    px, py = reverse_transform * (xgeo, ygeo)
    px, py = int(px + 0.5), int(py + 0.5)

    # make sure the pixel coordinates are actually within the raster
    maxx,maxy = ds.RasterXSize, ds.RasterYSize
    if px < 0 or px >= maxx or py < 0 or py >= maxy:
        return func.HttpResponse(f"Lat/lon coordinates resolved to col/row ({px}, {py}) and are outside of the raster extent ((0, 0), ({ds.RasterXSize}, {ds.RasterYSize}))", status_code=400)

    # get the band values at the pixel coordinates
    output = []
    for b in bands:
        band = ds.GetRasterBand(b)
        structval = band.ReadRaster(px, py, 1, 1, buf_type=gdal.GDT_Float32)
        result = struct.unpack('f', structval)[0]
        if result == band.GetNoDataValue():
            result = float('nan')
        output.append({'band':b, 'value':result})

    # close the dataset
    ds = None

    # return the band values
    return func.HttpResponse(json.dumps(output), mimetype="application/json", status_code=200)

@app.route(route="get_ci_values", methods=["POST"])
def http_trigger_2(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # Make sure we have all expected input parameters and that they are valid
    try:
        req_body = req.get_json()
    except:
        return func.HttpResponse("Please pass a JSON object with {'haz_stats': {'mean' (float), 'std_dev' (float)}, [optional] 'realizations' (int), [optional] 'distributions' (string), [optional] 'confidence_level' (float)} fields in the request body", status_code=400)  
    else:         
        haz_stats = req_body.get('haz_stats')
        realizations = req_body.get('realizations') or 5
        distribution = req_body.get('distribution') or 'normal'
        confidence_level = req_body.get('confidence_level') or 0.9
    
    if not haz_stats or not isinstance(haz_stats, dict):
        return func.HttpResponse(f"Please pass a haz_stats object in the request body", status_code=400)
    try:
        mean = haz_stats['mean']
        std_dev = haz_stats['std_dev']
    except:
        return func.HttpResponse(f"Please both 'mean' (float) and 'std_dev' (float) properties in the 'haz_stats' parameter", status_code=400) 
    
    if not mean or not isinstance(mean, float):
        return func.HttpResponse(f"Please pass a valid mean value in the haz_stats parameter", status_code=400)
    
    if not std_dev or not isinstance(std_dev, float):
        return func.HttpResponse(f"Please pass a valid std_dev value in the haz_stats parameter", status_code=400)

    if not realizations or not isinstance(realizations, int):
        return func.HttpResponse(f"Please pass valid realizations value in the request body or omit this parameter", status_code=400)
    
    if not distribution or not isinstance(distribution, str):
        return func.HttpResponse(f"Please pass a valid distribution value in the request body or omit this parameter", status_code=400)
    
    if not confidence_level or not isinstance(confidence_level, float):
        return func.HttpResponse(f"Please pass a valid confidence_level value in the request body or omit this parameter", status_code=400)
    
    result = confidence_interval_values(haz_stats, realizations, distribution, confidence_level)
    if result is None:
        return func.HttpResponse(f"only normal distribution is currently implemented", status_code=400)
    else:
        return func.HttpResponse(json.dumps(result), mimetype="application/json", status_code=200)