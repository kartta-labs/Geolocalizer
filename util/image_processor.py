# Copyright 2021 The Kartta Labs Authors.
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

"""Image processing module for OCR.

This module enables the caller to send arbitrary sized images to the Vision API.
The Vision API has a limit of 20 MB file size. This module takes in a large
image and divides it into two parts each time, once horizontally and once
vertically until the 20 MB size limit is reached. Then it sends the image
patches to the Vision API.
"""
from __future__ import division
from __future__ import print_function

from functools import partial
import io
import os
import tempfile
import uuid

from enum import Enum
from PIL import Image

from google.cloud import storage
from google.cloud import vision

vision_client = vision.ImageAnnotatorClient()
storage_client = storage.Client()


class Axis(Enum):
  VERTICAL = 'y'
  HORIZONTAL = 'x'


def call_vision_api(uri, max_size_megabytes=20, overlap=0.25):
  """Stores image in local directory, calls the vision API, and returns the response.

  Args:
    uri: 'https://i.stack.imgur.com/WiDpa.jpg'.
    max_size_megabytes: Max size of a file specified by the Vision API.
    overlap: Customizable overlap percentage.

  Returns:
  Response of the Vision API (https://cloud.google.com/vision/docs/ocr).
  """
  if not uri:
    raise ValueError('Please provide a URI.')
  folder_name = tempfile.mkdtemp()
  image_file = folder_name + '/original'

  with open(image_file, 'w') as file_obj:
    storage_client.download_blob_to_file(uri, file_obj)
  return _call_vision_api_helper(image_file, max_size_megabytes, overlap)


def _call_vision_api_helper(image_file, max_size_megabytes, overlap):
  """If the file size is larger, divides the image in two before sending to OCR.

  Calls the Vision API OCR directly if the file size is less than 20 MB.
  If the file size is larger, it divides the original image in two and calls
  itself recursively until the sub images meet the API size requirements.

  Args:
    image_file: Path to image file.
    max_size_megabytes: Max size of a file specified by the Vision API.
    overlap: Customizable overlap percentage.

  Returns:
    The Vision API response.
  """
  image_object = Image.open(image_file)
  width, height = image_object.size
  file_size = os.path.getsize(image_file)
  max_size_bytes = max_size_megabytes * 1024 * 1024

  with io.open(image_file, 'rb') as im_file:
    content = im_file.read()

  if file_size < max_size_bytes:
    image = vision.types.Image(content=content)
    response = vision_client.document_text_detection(image=image)
    return response

  elif width >= height:
    left_file, right_file, offset = _divide_image_left_and_right(image_file,
                                                                 overlap)
    os.remove(image_file)
    left_response = _call_vision_api_helper(left_file, max_size_bytes,
                                            overlap)

    right_response = _call_vision_api_helper(right_file, max_size_bytes,
                                             overlap)

    response = _merge_responses(offset, left_response, right_response,
                                Axis.HORIZONTAL)
    return response

  else:
    top_file, bottom_file, offset = _divide_image_top_and_bottom(image_file,
                                                                 overlap)
    os.remove(image_file)
    top_response = _call_vision_api_helper(top_file, max_size_bytes,
                                           overlap)

    bottom_response = _call_vision_api_helper(bottom_file, max_size_bytes,
                                              overlap)
    response = _merge_responses(offset, bottom_response, top_response,
                                Axis.VERTICAL)
    return response


def _divide_image_left_and_right(image_file, overlap):
  """Takes in an image and divides it vertically according to the overlap.

  Args:
    image_file: Image file.
    overlap: Customizable overlap percentage.

  Returns:
    A left file, right file and the offset to later
    be added when merging responses.
  """
  image_object = Image.open(image_file)
  width, height = image_object.size
  x_overlap = width * overlap

  left_x = int((width + x_overlap)/2)
  right_x = int((width - x_overlap)/2)
  offset = right_x

  left_sub_image = (0, 0, left_x, height)
  right_sub_image = (right_x, 0, width, height)

  left = image_object.crop(left_sub_image)
  right = image_object.crop(right_sub_image)

  left_file = 'tmp/{}.jpg'.format(str(uuid.uuid4()))
  left.save(left_file)

  right_file = 'tmp/{}.jpg'.format(str(uuid.uuid4()))
  right.save(right_file)

  return left_file, right_file, offset


def _divide_image_top_and_bottom(image_file, overlap):
  """Takes in an image and divides it horizontally according to the overlap.

  Args:
    image_file: Image file.
    overlap: Customizable overlap percentage.

  Returns:
    A top file, bottom file and the offset to later
    be added when merging responses.
  """

  image_object = Image.open(image_file)
  width, height = image_object.size
  y_overlap = height * overlap

  top_y = int((height + y_overlap)/2)
  bottom_y = int((height - y_overlap)/2)
  offset = bottom_y

  top_sub_image = (0, 0, width, top_y)
  bottom_sub_image = (0, bottom_y, width, height)

  top = image_object.crop(top_sub_image)
  bottom = image_object.crop(bottom_sub_image)

  top_file = 'tmp/{}.jpg'.format(str(uuid.uuid4()))
  top.save(top_file)

  bottom_file = 'tmp/{}.jpg'.format(str(uuid.uuid4()))
  bottom.save(bottom_file)

  return top_file, bottom_file, offset


def _add_offset(offset, element, axis):
  """Adds the offset to the x coordinates of the feature bounding boxes.

  Args:
    offset: Right sub image upper x value.
    element: Document features from the API response.
    axis: The axis to which the offset will be added.
  """
  for vertex in element.bounding_box.vertices:
    if axis == Axis.HORIZONTAL:
      vertex.x += offset
    if axis == Axis.VERTICAL:
      vertex.y += offset


def _merge_responses(offset, sub_response1, sub_response2, axis):
  """Merges responses from the cropped images.

  Args:
    offset: The image's x or y start point on the original image.
    sub_response1: Vision API response from the left or bottom image file.
    sub_response2: Vision API response from the right or top image file.
    axis: Merge direction.

  Returns:
    Full text annotations merged response.
  """
  response1_text = sub_response1.full_text_annotation.text
  response2_text = sub_response2.full_text_annotation.text

  merged_text = '{} {}'.format(response1_text, response2_text)

  sub_response1.full_text_annotation.text = merged_text

  custom_merged = {'full_text_annotation': sub_response1.full_text_annotation}

  merged_response = custom_merged['full_text_annotation']

  if axis == Axis.HORIZONTAL:
    add_offset_partial = partial(_add_offset, axis=Axis.HORIZONTAL)
  elif axis == Axis.VERTICAL:
    add_offset_partial = partial(_add_offset, axis=Axis.VERTICAL)

  for page in sub_response2.full_text_annotation.pages:
    for block in page.blocks:
      for paragraph in block.paragraphs:
        for word in paragraph.words:
          for symbol in word.symbols:
            add_offset_partial(offset, symbol)
          add_offset_partial(offset, word)
        add_offset_partial(offset, paragraph)
      add_offset_partial(offset, block)
    merged_response.pages.append(page)
  return custom_merged
