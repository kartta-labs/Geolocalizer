"""Main module for setting up google cloud function
https://cloud.google.com/functions/docs/writing/
"""
import os
import json

from geolocalizer import Geolocalizer

def geolocalize_map(request):
    """
    Args:
        request (flask.Request): HTTP request object
        JSON example: {"uri": "https://i.stack.imgur.com/WiDpa.jpg"}
    """
    request_json = request.get_json()
    if request.args and 'uri' in request.args:
        uri = request.args.get('uri')
    elif request_json and 'uri' in request_json:
        uri = request_json['uri']
    else:
        return f'No uri given!'

    # Environment variables when create GCF
    API_KEY = os.environ.get('GEOLOCALIZATION_API_KEY', None)
    if not API_KEY:
        return f'No API_KEY found'

    # TODO(zhouwubai): make it singleton
    geolocalizer = Geolocalizer(API_KEY)
    text, candidates = geolocalizer.geolocalize(uri)
    return json.dumps({"text": text, "candidates": candidates})
