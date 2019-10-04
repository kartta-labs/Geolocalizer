# Copyright 2019 The Kartta Labs Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This is a class to geolocalize a raster map.

This code uses Google Vision API to detect the text in a raster map. Then, it
sends the results to Google Geocoding API to guess where the map belongs to.
"""
import re
import googlemaps

from google.cloud import language
from google.cloud import vision
from google.cloud.language import enums
from google.cloud.language import types


class Geolocalizer(object):
  """Geolocalizes a given raster map."""
  _CONFIDENCE_THRESHOLD = 0.9

  def __init__(self, api_key):
    if not api_key:
      raise ValueError('A Google Maps Geocoding API key is required.')
    self.gmaps = googlemaps.Client(key=api_key)
    self.vision_client = vision.ImageAnnotatorClient()
    self.nlp_client = language.LanguageServiceClient()

  def _detect_texts(self, uri):
    """Detects text in the file given by a uri."""
    if not uri:
      raise ValueError('No URI was given.')
    image = vision.types.Image()
    image.source.image_uri = uri
    response = self.vision_client.document_text_detection(image=image)
    if response.error.code:
      raise Exception('Something went wrong with the Vision API:' +
                      str(response.error))
    if not response.full_text_annotation.pages:
      return None
    return response.full_text_annotation.pages[0]

  def _process_and_combine_texts(self, texts):
    """Processes the recognized texts and combines them to form a text corpus."""
    if not texts:
      return None
    words = ''
    for block in texts.blocks:
      for paragraph in block.paragraphs:
        if paragraph.confidence < self._CONFIDENCE_THRESHOLD:
          continue
        for word in paragraph.words:
          symbols = ''
          for symbol in word.symbols:
            symbols += symbol.text
            # Add a space for breaks.
            if symbol.property.detected_break.type is not 0:
              symbols += ' '
          words += symbols
    # Remove special characters. More processing can happen here, such as
    # removing stop words, etc.
    words = re.sub('[^0-9A-Za-z]+', ' ', words)
    if not words:
      return None
    addressess = self._analyze_entities(words)
    return addressess

  def _analyze_entities(self, text):
    """Analyzez the text and derives insights from it, such as addresses and locations"""
    document = language.types.Document(content=text,type=language.enums.Document.Type.PLAIN_TEXT)
    response = self.nlp_client.analyze_entities(document=document, encoding_type='UTF32')
    addresses = ''
    for entity in response.entities:
      if entity.type == enums.Entity.Type.ADDRESS or entity.type == enums.Entity.Type.LOCATION:
        addresses += entity.name + ' '
    return addresses

  def _geocode(self, text):
    """Returns the candidate geolocation for a textual query."""
    if not text:
      return None
    geocoding_results = self.gmaps.geocode(text)
    if not geocoding_results:
      return None
    candidates = []
    for result in geocoding_results:
      candidates.append(result['geometry']['location'])
    return candidates

  def geolocalize(self, uri):
    """Returns the geolocaltion of an image given by the uri."""
    texts = self._detect_texts(uri)
    text_blob = self._process_and_combine_texts(texts)
    candidates = self._geocode(text_blob)
    return (text_blob, candidates)
