import os
import json

from geolocalizer import Geolocalizer

def hello_world(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    request_json = request.get_json()
    if request.args and 'message' in request.args:
        return request.args.get('message')
    elif request_json and 'message' in request_json:
        return request_json['message']
    else:
        return f'Hello World!'

def geo_localize_image_map(request, mock=False):
    """
    Args:
        request (flask.Request): HTTP request object
        Json example: {"uri": "https://i.stack.imgur.com/WiDpa.jpg"}
    """
    if mock:
        uri = request['uri']
    else:
        request_json = request.get_json()
        if request.args and 'uri' in request.args:
            uri = request.args.get('uri')
        elif request_json and 'uri' in request_json:
            uri = request_json['uri']
        else:
            return f'No uri given!'

    API_KEY = os.environ.get('GEOLOCALIZATION_API_KEY', None)
    if not API_KEY:
        return f'No API_KEY found'

    # TODO(zhouwubai): make it singleton
    geolocalizer = Geolocalizer(API_KEY)
    text, candidates = geolocalizer.geolocalize(uri)
    return json.dumps({"text": text, "candidates": candidates})

if __name__ == '__main__':
    uri = "https://raw.githubusercontent.com/spatial-computing/map-ocr-ground-truth/master/maps/1920-1.png"
    mock_request = {"uri": uri}
    print(geo_localize_image_map(mock_request, True))
