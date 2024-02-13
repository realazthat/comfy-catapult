<!--

WARNING: This file is auto-generated. Do not edit directly.
SOURCE: `README.md.jinja2`.

-->
<!-- Note: This file is a jinja2 template of a Markdown file.                -->

<!-- Note: This is so that we can include working examples.                  -->

# README

**Warning:** Very raw and unmaintained code. Use at your own risk. Mainly
intended as a starting point.

## What is it?

Comfy Catapult is a library for scheduling and running ComfyUI workflows from a
Python program, via the existing API endpoint. ComfyUI typically works by
hosting this API endpoint for its user interface.

This makes it easier for you to make workflows via the UI, and then use it from
a program.

### Scheduling a job

From
[`examples/sdxlturbo_example_catapulter.py`](examples/sdxlturbo_example_catapulter.py):

````py
async def RunExampleWorkflow(*, job_info: ExampleWorkflowInfo):

  # You have to write this function, to change the workflow_dict as you like.
  await PrepareWorkflow(job_info=job_info)

  # Here the magic happens, the job is submitted to the ComfyUI server.
  job_info.job_history_dict = await job_info.catapult.Catapult(
      job_id=job_info.job_id,
      prepared_workflow=job_info.workflow_dict,
      important=job_info.important)

  # Now that the job is done, you have to write something that will go and get
  # the results you care about, if necessary.
  await DownloadResults(job_info=job_info)
````

````py
class ExampleWorkflowInfo:
  # Direct wrapper around the ComfyUI API.
  client: ComfyAPIClientBase
  # Job scheduler (the main point of this library).
  catapult: ComfyCatapultBase
  # Something to help with retrieving files from the ComfyUI storage.
  remote: RemoteFileAPIBase
  comfy_api_url: str

  # This should be the workflow json as a dict.
  workflow_template_dict: dict
  # This should begin as a deep copy of the template.
  workflow_dict: dict
  # This will hold the node ids that we must have results for.
  important: List[NodeID]

  # Make this any string unique to this job.
  job_id: str

  # When the job is complete, this will be the `/history` json/dictionary for
  # this job.
  job_history_dict: dict | None

  # These are inputs that modify this particular workflow.
  ckpt_name: str | None
  positive_prompt: str
  negative_prompt: str
  # For this particular workflow, this will define the path to the output image.
  output_path: Path
````

## Related Projects

- [comfyui-deploy](https://github.com/BennyKok/comfyui-deploy).
- [ComfyUI script_examples](https://github.com/comfyanonymous/ComfyUI/tree/master/script_examples).
- [ComfyUI-to-Python-Extension](https://github.com/pydn/ComfyUI-to-Python-Extension).
- [ComfyScript](https://github.com/Chaoses-Ib/ComfyScript)
- [hordelib](https://pypi.org/project/hordelib/)
- [ComfyUI_NetDist](https://github.com/city96/ComfyUI_NetDist)
- [ComfyUI-Serving-Toolkit](https://github.com/matan1905/ComfyUI-Serving-Toolkit)
- [comfyui-python-api](https://github.com/andreyryabtsev/comfyui-python-api)

## Getting Started

### Exporting workflows in the API json format

In ComfyUI web interface:

1. Open settings (gear box in the corner).
2. Enable the ability to export in the API format, `Enable Dev mode Options`.
3. Click new menu item `Save (API format)`.

![ComfyUI API format export instructions](assets/comfy-export-instructions.png)

### Example workflow: Prepare ComfyUI

**If you don't want to try the example workflow, you can skip this section.**

You need to get `sd_xl_turbo_1.0_fp16.safetensors` into the ComfyUI model
directory.

Hugging Face page:
[huggingface.co/stabilityai/sdxl-turbo/blob/main/sd_xl_turbo_1.0_fp16.safetensors](https://huggingface.co/stabilityai/sdxl-turbo/blob/main/sd_xl_turbo_1.0_fp16.safetensors).

Direct download link:
[huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors](huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors).

### Download the example workflow, and export it in the API format

**This is optional, you can use the example workflow in `test_data/` instead and
skip this step.**

```bash
# Download the workflow:
wget https://github.com/comfyanonymous/ComfyUI_examples/raw/master/sdturbo/sdxlturbo_example.png

# 1. Open the Workflow in ComfyUI and export it. AFAIK there isn't a nice way
# to automated this right now.
#
# 2, Save to `./sdxlturbo_example_api.json`.
#
# Or just use `test_data/sdxlturbo_example_api.json`.
```

### Install as a library from git and run the examples

```bash
# Inside your environment:
pip install git+https://github.com/realazthat/comfy-catapult.git
# Or (inside your environment):
git clone https://github.com/realazthat/comfy-catapult.git
cd comfy-catapult
pip install .



# If you set this environment variable, you don't have to specify it as an
# argument.
export COMFY_API_URL=http://127.0.0.1:8188
# Note, in WSL2 you may have to use the following if ComfyUI is running on the
# Windows side:
export COMFY_API_URL=http://host.docker.internal:8188


python -m comfy_catapult.examples.sdxlturbo_example_catapulter \
  --api_workflow_json_path "$PWD/sdxlturbo_example_api.json" \
  --tmp_path "$PWD/.deleteme/tmp/" \
  --output_path "$PWD/.deleteme/output.png" \
  --positive_prompt "amazing cloudscape, towering clouds, thunderstorm, awe" \
  --negative_prompt "dull, blurry, nsfw"

# Optional if you don't want to set the environment variable:
#   --comfy_api_url "..."

# Done! Now $PWD/.deleteme/output.png should contain the output image.

# Some other examples:
python -m comfy_catapult.examples.add_a_node
python -m comfy_catapult.examples.using_pydantic



```

- Examine
  [`examples/sdxlturbo_example_catapulter.py`](examples/sdxlturbo_example_catapulter.py)
  to see how to use the main `ComfyCatapult` library.
- Examine
  [`test_data/sdxlturbo_example_api.json`](test_data/sdxlturbo_example_api.json)
  to see the API format. This will be necessary in order to programmatically set
  the proper inputs for the workflow.
  - (Optional) See [`examples/using_pydantic.py`](examples/using_pydantic.py)
    for how to parse the API format into the Pydantic models schema for easier
    navigation.
  - (Optional) See [`examples/add_a_node.py`](examples/add_a_node.py) for how to
    add a new node to a workflow. This is useful when you need to add nodes at
    runtime (such as adding a bunch of LoadImage nodes).
- See [`comfy_catapult/catapult_base.py`](comfy_catapult/catapult_base.py) for
  the main library interface.
- (Optional) See [`comfy_catapult/catapult.py`](comfy_catapult/catapult_base.py)
  for the main library implementation.
- (Optional) See
  [`comfy_catapult/api_client_base.py`](comfy_catapult/api_client_base.py) for
  the direct ComfyUI API endpoint client library interface; you don't need to
  use this usually.
- (Optional) For those who want to do use the raw API themselves and learn how
  it works: Examine
  [`comfy_catapult/api_client.py`](comfy_catapult/api_client.py) to see the API
  client implementation if you want to directly interface with ComfyUI endpoints
  yourself.
  - (Optional) Also see
    [ComfyUI/server.py](https://github.com/comfyanonymous/ComfyUI/blob/977eda19a6471fbff253dc92c3c2f1a4a67b1793/server.py#L99)
    (pinned to a specific commit) for the server `@routes` endpoint
    implementations.

### Development; install dependencies and run the examples

This is if you are intending on contributing or altering the library itself.

```bash

git clone https://github.com/realazthat/comfy-catapult.git
cd comfy-catapult
pip install -r requirements.txt


# Run the example workflow:
PYTHONPATH=$PYTHONPATH:$PWD python examples/sdxlturbo_example_catapulter.py \
  --api_workflow_json_path "$PWD/sdxlturbo_example_api.json"
  --tmp_path "$PWD/.deleteme/tmp/" \
  --output_path "$PWD/.deleteme/output.png" \
  --positive_prompt "amazing cloudscape, towering clouds, thunderstorm, awe" \
  --negative_prompt "dull, blurry, nsfw"


```

### Parsing the API format into the Pydantic models schema for easier navigation

From [`examples/using_pydantic.py`](examples/using_pydantic.py):

````py
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

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

````

### Adding a new node to a workflow

From [`examples/add_a_node.py`](examples/add_a_node.py):

````py
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

from pathlib import Path

from comfy_catapult.comfy_schema import (APIWorkflow, APIWorkflowNodeInfo,
                                         APIWorkflowNodeMeta)
from comfy_catapult.comfy_utils import GenerateNewNodeID

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

path_to_comfy_input = Path('/path/to/ComfyUI/input')
path_to_image = path_to_comfy_input / 'image.jpg'
rel_path_to_image = path_to_image.relative_to(path_to_comfy_input)

# Add a new LoadImage node to the workflow.
new_node_id = GenerateNewNodeID(workflow=api_workflow)
api_workflow.root[new_node_id] = APIWorkflowNodeInfo(
    inputs={
        'image': f'{rel_path_to_image} [input]',
        'upload': 'image',
    },
    class_type='LoadImage',
    _meta=APIWorkflowNodeMeta(title='My Loader Title'))

print(api_workflow.model_dump_json())

````

## Known to work on

- **Python 3.11.4**, WSL2/Windows11, Ubuntu 22.04.2 LTS

## Limitations

- ETA estimator isn't working
- Sometimes the job ends early but no error is sent back from the server. Error
  is detected because not all nodes have executed, but the error is opaque
  (check the server logs for the error).

## TODO

- [ ]  Helpers should support remote/cloud storage for ComfyUI input/output/model
  directories. (Currently only supports local paths.)
- [ ]  ETA Estimator.
- [ ]  Make sure the schema can parse the formats even if the format adds new
  fields.

## Comitting

1. `bash scripts/pre.sh`.
2. Check for modified files: `git status`
3. Stage any modified: `git add -u`
4. If any modified files: Go to step 1.
5. `git commit -m "..."`.

## Releasing

1. Bump version in `README.template.md`, `setup.py`, `CHANGELOG.md`.
2. `REL_VER=...`.
3. `git commit -nam "Release $REL_VER"`.
4. `git push`.
5. `git tag $REL_VER`.
6. `git push --tags`.
7. Create a GitHub release.
