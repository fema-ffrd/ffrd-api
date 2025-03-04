# Introduction 
An open-source API deployed as a Python Azure Function to allow a client to query for a raster value at a specified set of coordinates in a specified raster file
(preferably in COG format). An alternate version of the API deployed as a FastAPI application (with associated requirements file) is available for users who don't have access to Microsoft Azure.

# Running Locally using Visual Studio Code
1.	Clone the repository to a local directory.
2.	Install Python 3.11 on your system.
3.	Use Python 3.11 to create a virtual environment in the local directory using the `venv` command (preferably called `.venv`).
4.  Install the Azure Functions extension in VS Code.
5.  Open the project in VS Code and set the Python interpreter to `.\.venv\Scripts\python.exe`.
6.  Set an environment variable *AZURE_STORAGE_CONNECTION_STRING* to the connection string to an Azure Storage account where the raster files are stored.
7.  Use the Debug panel to start the application locally and debug its code.

# Calling the API
POST https://{host}/api/get_values

## Post body should be a JSON object (schema defined in swagger.json)
- 'file': a string containing the name of the file in the storage account, not the full path
- 'bands': an array containing at least one integer indicating the raster band(s) to read data from
- 'lat': a floating point latitude coordinate in decimal degrees
- 'lon': a floating point longitude coordinate in decimal degrees