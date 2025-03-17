from typing import Optional
import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing_extensions import Annotated
import logging
import osgeo
from osgeo import gdal
from affine import Affine
import os
import struct
from ci import confidence_interval_values

# TODO: set app settings for access to S3?
#os.environ["AZURE_STORAGE_CONNECTION_STRING"] = f""

gdal.osr.UseExceptions()

class InputData(BaseModel):
    file: str
    bands: list[int]
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]

class OutputData(BaseModel):
    band: int
    value: float | None

class InputCIHazStats(BaseModel):
    mean: float
    std_dev: float

class InputCIData(BaseModel):
    haz_stats: InputCIHazStats
    realizations: Optional[int] = 5
    distribution: Optional[str] = 'normal'
    confidence_level: Optional[float] = 0.9

class OutputCIData(BaseModel):
    lower_val: float
    upper_val: float
    lower_bound: str
    upper_bound: str

app = FastAPI()

@app.post("/get_values", response_model=list[OutputData])
async def get_values(req: InputData):
    logging.info('API processed a request.')

    # Make sure we have all expected input parameters and that they are valid
    try:
        file = req.file
        bands = req.bands
        lat = req.lat
        lon = req.lon
    except:
        return Response(
            "Please pass a JSON object with {'file' (string), 'bands' (int array), 'lat' (float), 'lon' (float)} fields in the request body",
            status_code=400
        )        

    if not file or not isinstance(file, str) or len(file) == 0:
        return Response(f"Please pass a file name in the request body", status_code=400)

    if not bands or not isinstance(bands, list) or len(bands) == 0:
        return Response(f"Please pass an array containing at least one band in the request body", status_code=400)
    
    if not lat or not (isinstance(lat, float) or isinstance(lat, int)) or not -90 <= lat <= 90:
        return Response(f"Please pass a valid latitude in the request body", status_code=400)
    
    if not lon or not (isinstance(lon, float) or isinstance(lon, int)) or not -180 <= lon <= 180:
        return Response(f"Please pass a valid longitude in the request body", status_code=400)
    
    # Make sure the file exists
    try:
        # TODO: Update this to point to S3 instead?
        stg = f"/vsiaz/data/{file}"
        ds = gdal.Open(stg, gdal.GA_ReadOnly)
    except:
        return Response(f"File {file} cannot be opened or does not exist", status_code=400)
    
    # make sure the bands specified in the parameters actually exist in the file
    for b in bands:
        if b < 1 or b > ds.RasterCount:
            return Response(f"Band {b} does not exist in the raster", status_code=400)
    
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
        return Response(f"Lat/lon coordinates resolved to col/row ({px}, {py}) and are outside of the raster extent ((0, 0), ({ds.RasterXSize}, {ds.RasterYSize}))", status_code=400)

    # get the band values at the pixel coordinates
    output = []
    for b in bands:
        band = ds.GetRasterBand(b)
        structval = band.ReadRaster(px, py, 1, 1, buf_type=gdal.GDT_Float32)
        result = struct.unpack('f', structval)[0]
        if result == band.GetNoDataValue():
            result = None
        output.append(OutputData(band=b, value=result))

    # close the dataset
    ds = None

    # return the band values
    return output

@app.post("/get_ci_values", response_model=OutputCIData)
async def get_ci_values(req: InputCIData):
    logging.info('API processed a request.')
    print(req)

    # Make sure we have all expected input parameters and that they are valid
    try:
        haz_stats = req.haz_stats
        realizations = req.realizations
        distribution = req.distribution
        confidence_level = req.confidence_level
    except:
        return Response("Please pass a JSON object with {'haz_stats': {'mean' (float), 'std_dev' (float)}, [optional] 'realizations' (int), [optional] 'distributions' (string), [optional] 'confidence_level' (float)} fields in the request body", status_code=400)  
    
    if not haz_stats or not isinstance(haz_stats, InputCIHazStats):
        return Response(f"Please pass a haz_stats object in the request body", status_code=400)
    try:
        mean = haz_stats.mean
        std_dev = haz_stats.std_dev
    except:
        return Response(f"Please both 'mean' (float) and 'std_dev' (float) properties in the 'haz_stats' parameter", status_code=400) 
    
    if not mean or not isinstance(mean, float):
        return Response(f"Please pass a valid mean value in the haz_stats parameter", status_code=400)
    
    if not std_dev or not isinstance(std_dev, float):
        return Response(f"Please pass a valid std_dev value in the haz_stats parameter", status_code=400)
    
    result = confidence_interval_values({'mean': haz_stats.mean, 'std_dev': haz_stats.std_dev}, realizations, distribution, confidence_level)
    if result is None:
        return Response(f"only normal distribution is currently implemented", status_code=400)
    else:
        return result

if __name__ == "__main__":
    uvicorn.run(app=app, host="127.0.0.1", port=8000, log_level="debug")