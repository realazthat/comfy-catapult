# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

# SNIPPETSTART
from comfy_catapult.comfy_schema import APIWorkflow

api_workflow_json_str: str = """
{
  "1": {
    "inputs": {
      "image": "{remote_image_path} [input]",
      "upload": "image"
    },
    "class_type": "LoadImage",
    "_meta": {
      "title": "My Loader Title"
    }
  },
  "25": {
    "inputs": {
      "images": [
        "8",
        0
      ]
    },
    "class_type": "PreviewImage",
    "_meta": {
      "title": "Preview Image"
    }
  }
}
"""
api_workflow: APIWorkflow = APIWorkflow.model_validate_json(
    api_workflow_json_str)

# Or, if you have a APIWorkflow, and you want to deal with a dict instead:
api_workflow_dict = api_workflow.model_dump()

# Or, back to json:
api_workflow_json = api_workflow.model_dump_json()

# See comfy_catapult/comfyui_schema.py for the schema definition.

print(api_workflow_json)
# SNIPPETEND
