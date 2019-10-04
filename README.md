This repository contains the source code for a tool to geolocalize a raster map.

This code uses Google Vision API to detect the text in a raster map. Then, it
sends the textual results to Google NLP API to identify addresses and locations.
These entities are then sent to Google Geocoding API to guess where the map belongs to.

## How to use
This code needs access to Google Cloud tools such as the Vision and Geocoding API's.
Therefore, you must authenticate to the Cloud API, using a service accout. You will find
more information here: https://cloud.google.com/docs/authentication/getting-started

After authentication (i.e., setting the GOOGLE_APPLICATION_CREDENTIALS environment variable)
you can use this tool like this:
```python
geolocalizer = Geolocalizer(key='Add Your Key Here')
detected_text, candidate_locations = geolocalizer.geolocalize(uri_to_the_map_image)
```
