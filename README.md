<!-- WARNING: This file is auto-generated. Do not edit directly.             -->
<!-- SOURCE: `README.template.md`.                                           -->
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

## Getting Started

### Exporting workflows in the API json format

In ComfyUI web interface:

1. Click settings.
2. Enable the ability to export in the API format.
3. Click `Save (API format)`.

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

# Save to `./sdxlturbo_example_api.json`.
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


# Now $PWD/.deleteme/output.png should contain the output image.

python -m comfy_catapult.examples.add_a_node
python -m comfy_catapult.examples.using_pydantic



```

- Examine
  [`comfy_catapult/examples/sdxlturbo_example_catapulter.py`](comfy_catapult/examples/sdxlturbo_example_catapulter.py)
  to see how to use the main `ComfyCatapult` library.
- Examine
  [`test_data/sdxlturbo_example_api.json`](test_data/sdxlturbo_example_api.json)
  to see the API format.
- See [`comfy_catapult/catapult_base.py`](comfy_catapult/catapult_base.py) for
  the main library interface.
- See [`comfy_catapult/catapult.py`](comfy_catapult/catapult_base.py) for the
  main library implementation.
- See [`comfy_catapult/api_client_base.py`](comfy_catapult/api_client_base.py)
  for the direct ComfyUI API endpoint client library interface; you don't need
  to use this usually.
- For those who want to do use the raw API themselves and learn how it works:
  Examine [`comfy_catapult/api_client.py`](comfy_catapult/api_client.py) to see
  the API client implementation if you want to directly interface with ComfyUI
  endpoints yourself.
  - Also see
    [ComfyUI/server.py](https://github.com/comfyanonymous/ComfyUI/blob/977eda19a6471fbff253dc92c3c2f1a4a67b1793/server.py#L99)
    (pinned to a specific commit) for the server `@routes` endpoint
    implementations.
- See
  [`comfy_catapult/examples/add_a_node.py`](comfy_catapult/examples/add_a_node.py)
  for how to add a new node to a workflow.
- See
  [`comfy_catapult/examples/using_pydantic.py`](comfy_catapult/examples/using_pydantic.py)
  for how to parse the API format into the Pydantic models schema for easier
  navigation.

### Development; install dependencies and run the examples

This is if you are intending on contributing or altering the library itself.

```bash

git clone https://github.com/realazthat/comfy-catapult.git
cd comfy-catapult
pip install -r requirements.txt


# Run the example workflow:
PYTHONPATH=$PYTHONPATH:$PWD python comfy_catapult/examples/sdxlturbo_example_catapulter.py \
  --api_workflow_json_path "$PWD/sdxlturbo_example_api.json"
  --tmp_path "$PWD/.deleteme/tmp/" \
  --output_path "$PWD/.deleteme/output.png" \
  --positive_prompt "amazing cloudscape, towering clouds, thunderstorm, awe" \
  --negative_prompt "dull, blurry, nsfw"


```

### Scheduling a job

From `comfy_catapult/examples/sdxlturbo_example_catapulter.py`:

```py
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project require contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import asyncio
import sys
import uuid
from pprint import pprint
from typing import List

from comfy_catapult.api_client import ComfyAPIClient, ComfyAPIClientBase
from comfy_catapult.catapult import ComfyCatapult, JobStatus
from comfy_catapult.comfy_config import RemoteComfyConfig
from comfy_catapult.comfy_schema import (APIHistoryEntry, APIObjectInfo,
                                         APIObjectInputTuple, APISystemStats,
                                         APIWorkflow, APIWorkflowInConnection,
                                         NodeID)
from comfy_catapult.comfy_utils import (DownloadPreviewImage, GetNodeByTitle,
                                        YamlDump)
from comfy_catapult.examples.utilities.sdxlturbo_parse_args import (Args,
                                                                    ParseArgs)
from comfy_catapult.remote_file_api_base import RemoteFileAPIBase
from comfy_catapult.remote_file_api_comfy import ComfySchemeRemoteFileAPI
from comfy_catapult.remote_file_api_generic import GenericRemoteFileAPI
from comfy_catapult.remote_file_api_local import LocalRemoteFileAPI
from comfy_catapult.url_utils import ToParseResult


async def amain():
  args = await ParseArgs()

  print('args:', file=sys.stderr)
  pprint(args._asdict(),
         stream=sys.stderr,
         indent=2,
         width=120,
         sort_dicts=False)
  comfy_api_url = args.comfy_api_url

  # These are used to insure that files are not written/read outside of the
  # comfy_input_url and comfy_output_url directories.
  comfy_config = RemoteComfyConfig(
      comfy_api_url=args.comfy_api_url,
      base_file_url=args.comfy_base_file_url,
      input_file_url=args.comfy_input_file_url,
      temp_file_url=args.comfy_temp_file_url,
      output_file_url=args.comfy_output_file_url,
  )

  # Read the workflow into a string.
  workflow_json_str: str = await args.api_workflow_json_path.read_text()

  # Parse it with the pydantic model so we can manipulate it more nicely than
  # with raw json, we'll use this as a template, and fill in the inputs to
  # customize it for this job.
  #
  # If you prefer, you can work with raw python dict conversion of the json.
  workflow: APIWorkflow
  workflow = APIWorkflow.model_validate_json(workflow_json_str)

  # Start a ComfyUI Client (provided in comfy_catapult.api_client).
  async with ComfyAPIClient(comfy_api_url=args.comfy_api_url) as comfy_client:

    # Utility to help download/upload files.
    remote = GenericRemoteFileAPI()
    # This maps comfy+http://comfy_host:port/folder_type/subfolder/filename to
    # the /view and /upload API endpoints.
    remote.Register(
        ComfySchemeRemoteFileAPI(comfy_api_urls=[comfy_config.comfy_api_url],
                                 overwrite=True))
    if comfy_config.base_file_url is not None:
      assert ToParseResult(comfy_config.base_file_url).scheme == 'file'

      # This one uses file:/// protocol on the local system. It is probably
      # faster. In the future, I hope to add other protocols, so this can be
      # used with other a choice remote storage systems as transparently as
      # possible.
      remote.Register(
          LocalRemoteFileAPI(upload_to_bases=[comfy_config.input_file_url],
                             download_from_bases=[
                                 comfy_config.output_file_url,
                                 comfy_config.temp_file_url
                             ]))

    # Now specialize the workflow for this job.
    important: List[NodeID] = []
    await PrepareWorkflow(client=comfy_client,
                          workflow=workflow,
                          args=args,
                          important=important)

    # Dump the ComfyUI server stats.
    system_stats: APISystemStats = await comfy_client.GetSystemStats()
    print('system_stats:', file=sys.stderr)
    print(YamlDump(system_stats.model_dump()), file=sys.stderr)

    async with ComfyCatapult(comfy_client=comfy_client,
                             debug_path=args.debug_path) as catapult:
      job_id = str(uuid.uuid4())

      # Launch the job.
      job_history_dict: dict = await catapult.Catapult(
          job_id=job_id,
          prepared_workflow=workflow.model_dump(),
          important=important)

      # Job is done.

      # Now, we can either trudge through job_history_dict, or we can convert it
      # to a pydantic model, which is easier to work with.
      job_history = APIHistoryEntry.model_validate(job_history_dict)

      status: JobStatus
      status, future = await catapult.GetStatus(job_id=job_id)
      print('status:', file=sys.stderr)
      print(YamlDump(status._asdict()), file=sys.stderr)
      print('job_history:', file=sys.stderr)
      print(YamlDump(job_history.model_dump()), file=sys.stderr)

      # Download Preview Image.
      await FinishWorkflow(comfy_api_url=comfy_api_url,
                           remote=remote,
                           workflow=workflow,
                           args=args,
                           job_history=job_history)


async def PrepareWorkflow(*, client: ComfyAPIClientBase, workflow: APIWorkflow,
                          args: Args, important: List[NodeID]):
  # Connect the inputs to `workflow` here.

  # Get nodes by title.

  _, load_checkpoint = GetNodeByTitle(workflow=workflow,
                                      title='Load Checkpoint')

  # Unfortunately, two nodes 'CLIP Text Encode (Prompt)' are same title.
  # So instead, we'll find 'SamplerCustom' and work backwards.
  _, sampler_custom = GetNodeByTitle(workflow=workflow, title='SamplerCustom')

  in_conn = sampler_custom.inputs['positive']
  assert isinstance(in_conn, APIWorkflowInConnection)
  positive_prompt_id = in_conn.output_node_id
  positive_prompt = workflow.root[positive_prompt_id]

  in_conn = sampler_custom.inputs['negative']
  assert isinstance(in_conn, APIWorkflowInConnection)
  negative_prompt_id = in_conn.output_node_id
  negative_prompt = workflow.root[negative_prompt_id]

  preview_image_id, _ = GetNodeByTitle(workflow=workflow, title='Preview Image')
  ############################################################################

  # Get the /object_info, because we sometimes need to correct the model name,
  # because the model name is inconsistent between windows and linux if it is in
  # a directory, depending on the ComfyUI's system. E.g 'sd_xl_turbo_1.0_fp16'
  # vs 'SDXL-TURBO\sd_xl_turbo_1.0_fp16.safetensors' vs
  # 'SDXL-TURBO/sd_xl_turbo_1.0_fp16.safetensors'.
  object_info: APIObjectInfo = await client.GetObjectInfo()

  object_info_entry = object_info.root[load_checkpoint.class_type]

  assert isinstance(object_info_entry.input.required, dict)
  # Inputs are stored as a list/tuple of two things: the type (usually a string)
  # and a dictionary like {default: ..., min: ..., max: ...}.
  chpt_name_entry = object_info_entry.input.required['ckpt_name']
  assert isinstance(chpt_name_entry, APIObjectInputTuple), type(chpt_name_entry)

  # Combo type is a weird type that isn't a string, but rather a list of actual
  # values that are valid to choose from, usually strings.
  assert isinstance(chpt_name_entry.type, list), type(chpt_name_entry.type)

  load_checkpoint_valid_models = []
  for item in chpt_name_entry.type:
    assert isinstance(item, str), (f'item must be str, but is {type(item)}')
    load_checkpoint_valid_models.append(item)
  ############################################################################
  # Set some stuff in the workflow api json.

  assert (
      'sd_xl_turbo_1.0_fp16.safetensors' == load_checkpoint.inputs['ckpt_name']
  ), ('sanity check, this is just what is in the workflow already.')

  if args.ckpt_name is not None:
    assert args.ckpt_name in load_checkpoint_valid_models, (
        f'ckpt_name must be one of {load_checkpoint_valid_models}, but is {args.ckpt_name}'
    )
    load_checkpoint.inputs['ckpt_name'] = args.ckpt_name

  positive_prompt.inputs['text'] = args.positive_prompt
  negative_prompt.inputs['text'] = args.negative_prompt
  negative_prompt.inputs['text'] = args.negative_prompt
  ############################################################################
  # Mark some nodes as required to be executed, in order for us to consider
  # the job done.
  important.append(preview_image_id)
  ############################################################################


async def FinishWorkflow(*, comfy_api_url: str, remote: RemoteFileAPIBase,
                         workflow: APIWorkflow, args: Args,
                         job_history: APIHistoryEntry):
  print('job_history:', file=sys.stderr)
  print(YamlDump(job_history.model_dump()), file=sys.stderr)

  preview_image_id, _ = GetNodeByTitle(workflow=workflow, title='Preview Image')

  # You are gonna want to look at how this function works.
  await DownloadPreviewImage(node_id=preview_image_id,
                             job_history=job_history,
                             field_path='images[0]',
                             comfy_api_url=comfy_api_url,
                             remote=remote,
                             local_dst_path=args.output_path)


asyncio.run(amain(), debug=True)
```

### Parsing the API format into the Pydantic models schema for easier navigation

From `comfy_catapult/examples/using_pydantic.py`:

```py
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project require contributions made to this file be licensed
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
```

### Adding a new node to a workflow

From `comfy_catapult/examples/add_a_node.py`:

```py
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project require contributions made to this file be licensed
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
```

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
