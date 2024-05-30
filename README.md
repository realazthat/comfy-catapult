<!--

WARNING: This file is auto-generated by snipinator. Do not edit directly.
SOURCE: `README.md.jinja2`.

-->
<!-- Note: This file is a jinja2 template of a Markdown file.                -->
<!--







-->

# <div align="center">![Comfy Catapult][24]</div>

<div align="center">
<!-- Icons from https://lucide.dev/icons/users -->
<!-- Icons from https://lucide.dev/icons/laptop-minimal -->

![**Audience:** Developers][25] ![**Platform:** Linux][26]

</div>

<p align="center">
  <strong>
    <a href="https://github.com/realazthat/comfy-catapult">🏠Home</a>
    &nbsp;&bull;&nbsp;
    <a href="#-features">🎇Features</a>
    &nbsp;&bull;&nbsp;
    <a href="#-installation">🔨Installation</a>
    &nbsp;&bull;&nbsp;
    <a href="#-usage">🚜Usage</a>
    &nbsp;&bull;&nbsp;
    <a href="#-documentation">📘Documentation</a>
    &nbsp;&bull;&nbsp;
    <a href="#-api">🤖API</a>
  </strong>
</p>

<p align="center">
  <strong>
    <a href="#-requirements">✅Requirements</a>
    &nbsp;&bull;&nbsp;
    <a href="#-command-line-options">💻CLI</a>
    &nbsp;&bull;&nbsp;
    <a href="#-docker-image">🐳Docker</a>
    &nbsp;&bull;&nbsp;
    <a href="#-limitations">🚸Limitations</a>
  </strong>
</p>

<div align="center">

![Top language][19] ![GitHub License][11] [![PyPI - Version][12]][13]
[![Python Version][18]][13]

**Python library to programmatically schedule ComfyUI workflows via the ComfyUI
API**

</div>

---

<div align="center">

| Branch        | Build Status              | Commits Since             | Last Commit        |
| ------------- | ------------------------- | ------------------------- | ------------------ |
| [Master][27]  | [![Build and Test][1]][2] | [![since tagged][14]][20] | ![last commit][16] |
| [Develop][28] | [![Build and Test][3]][4] | [![since tagged][15]][21] | ![last commit][17] |

</div>

```
ComfyUI API Endpoint <| <=  Comfy Catapult <=> HTTP Server <| <=  Public users
                     <|                                    <|
                     <|         Your python program        <| Your Webui/JS frontend
                     <|                                    <|
                     <|           Your workflows           <|
                     <|          Your HTTP server          <|
```

## What is it?

Comfy Catapult is a library for scheduling and running ComfyUI workflows from a
Python program, via the existing API endpoint. ComfyUI typically works by
hosting this API endpoint for its user interface.

This makes it easier for you to make workflows via the UI, and then use it from
a program.

## 🎇 Features

- ComfyUI API client
  ([interface](./comfy_catapult/api_client_base.py),
  [implementation](./comfy_catapult/api_client.py)).
- ComfyUI Workflow scheduler
  ([interface](./comfy_catapult/catapult_base.py),
  [implementation](./comfy_catapult/catapult.py)).
- ComfyUI API Pydantic Schema
  ([./comfy_catapult/comfy_schema.py](./comfy_catapult/comfy_schema.py)).
- Helpers to handle uploading and downloading files to/from ComfyUI.
- Simple CLI to execute workflows.

## 🔨 Installation

```bash
# Inside your environment:

# From pypi:
pip install comfy_catapult

# From git:
pip install git+https://github.com/realazthat/comfy-catapult.git@v2.2.0
```

## 🚜 Usage

## Related Projects

| Project                          | ComfyUI API Wrapper | Outsource Backend | Distribute Execution | Wrap Workflow | Studio |
| -------------------------------- | ------------------- | ----------------- | -------------------- | ------------- | ------ |
| [CushyStudio][31]                | ?                   | ?                 | ?                    | ?             | Yes    |
| [ComfyUI-Serving-Toolkit][30]    | X                   | ?                 | ?                    | Yes           | ?      |
| [ComfyUI_NetDist][29]            | X                   | ?                 | Yes                  | ?             | ?      |
| [ComfyUI script_examples][32]    | Yes                 | No                | No                   | No            | No     |
| [comfyui-python-api][5]          | ?                   | ?                 | ?                    | Yes           | ?      |
| [comfyui-deploy][6]              | ?                   | ?                 | ?                    | Yes           | ?      |
| [ComfyUI-to-Python-Extension][7] | ?                   | ?                 | ?                    | Yes           | ?      |
| [ComfyScript][8]                 | ?                   | ?                 | ?                    | Yes           | ?      |
| [hordelib][9]                    | ?                   | Yes               | ?                    | ?             | ?      |
| [comfyui-cloud][10]              | ?                   | Yes               | ?                    | ?             | ?      |
| [comfy_runner][22]               | ?                   | ?                 | ?                    | ?             | ?      |
| [ComfyUI-ComfyRun][23]           | ?                   | ?                 | ?                    | ?             | ?      |

## 📘 Documentation

### Scheduling a Job

From
[`comfy_catapult/catapult_base.py`](comfy_catapult/catapult_base.py):

````py
  async def Catapult(
      self,
      *,
      job_id: str,
      prepared_workflow: dict,
      important: Sequence[APINodeID],
      job_debug_path: Optional[Path] = None,
  ) -> dict:
    """Schedule a ComfyUI workflow job.

    Args:
        job_id (str): A unique identifier for the job. Note: This string must
          be unique, and must be slugified! Use python-slugify to slugify the
          string.
        prepared_workflow (dict): Workflow to submit.
        important (List[APINodeID]): List of important nodes (e.g output nodes we
          are interested in).
        job_debug_path (Path, optional): Path to save debug information. If
          None, will use sensible defaults.

    Raises:
        WorkflowSubmissionError: Failed to submit workflow.

    Returns:
        dict: The history of the job returned from the ComfyUI API.
    """
````

### Example usage:

From
[`examples/sdxlturbo_example_catapulter.py`](examples/sdxlturbo_example_catapulter.py):

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
  important: List[APINodeID]

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

````py
async def RunExampleWorkflow(*, job_info: ExampleWorkflowInfo):

  # You have to write this function, to change the workflow_dict as you like.
  await PrepareWorkflow(job_info=job_info)

  job_id: str = job_info.job_id
  workflow_dict: dict = job_info.workflow_dict
  important: List[APINodeID] = job_info.important

  # Here the magic happens, the job is submitted to the ComfyUI server.
  job_info.job_history_dict = await job_info.catapult.Catapult(
      job_id=job_id, prepared_workflow=workflow_dict, important=important)

  # Now that the job is done, you have to write something that will go and get
  # the results you care about, if necessary.
  await DownloadResults(job_info=job_info)
````

### Exporting workflows in the API json format

In ComfyUI web interface:

1. Open settings (gear box in the corner).
2. Enable the ability to export in the API format, `Enable Dev mode Options`.
3. Click new menu item `Save (API format)`.

![ComfyUI API format export instructions](.github/comfy-export-instructions.png)

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

### Run the examples

```bash


# If you set this environment variable, you don't have to specify it as an
# argument.
export COMFY_API_URL=http://127.0.0.1:8188
# Note, in WSL2 you may have to use the IP of the host to connect to ComfyUI.


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

### 🤖 API

- Examine [./examples/sdxlturbo_example_catapulter.py](./examples/sdxlturbo_example_catapulter.py) to
  see how to use the main `ComfyCatapult` library.
- Examine [./test_data/sdxlturbo_example_api.json](./test_data/sdxlturbo_example_api.json) to see
  the API format. This will be necessary in order to programmatically set the
  proper inputs for the workflow.
  - (Optional) See [./examples/using_pydantic.py](./examples/using_pydantic.py) for how
    to parse the API format into the Pydantic models schema for easier
    navigation.
  - (Optional) See [./examples/add_a_node.py](./examples/add_a_node.py) for how to
    add a new node to a workflow. This is useful when you need to add nodes at
    runtime (such as adding a bunch of LoadImage nodes).
- See [./comfy_catapult/catapult_base.py](./comfy_catapult/catapult_base.py) for the main
  library interface.
- (Optional) See [./comfy_catapult/catapult.py](./comfy_catapult/catapult.py) for the
  main library implementation.
- (Optional) See [./comfy_catapult/api_client_base.py](./comfy_catapult/api_client_base.py) for
  the direct ComfyUI API endpoint client library interface; you don't need to
  use this usually.
- (Optional) For those who want to do use the raw API themselves and learn how
  it works: Examine [./comfy_catapult/api_client.py](./comfy_catapult/api_client.py) to see
  the API client implementation if you want to directly interface with ComfyUI
  endpoints yourself.
  - (Optional) Also see
    [ComfyUI/server.py](https://github.com/comfyanonymous/ComfyUI/blob/977eda19a6471fbff253dc92c3c2f1a4a67b1793/server.py#L99)
    (pinned to a specific commit) for the server `@routes` endpoint
    implementations.

### Parsing the API format into the Pydantic models schema for easier navigation

From [./examples/using_pydantic.py](./examples/using_pydantic.py):

````py

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

From [examples/add_a_node.py](examples/add_a_node.py):

````py

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

### 💻 Command Line Options

<!---->
<img src="README.help.generated.svg" alt="Output of `python -m comfy_catapult.cli --help`" />
<!---->

## ✅ Requirements

- Python 3.10+
- ComfyUI server with API endpoint enabled.

### Known to work on

- WSL2/Windows11, Ubuntu 22.04.2 LTS: **Python
  3.10.0**.
- Ubuntu 20.04, Python `3.10.0`, tested in GitHub Actions
  workflow ([./.github/workflows/build-and-test.yml](./.github/workflows/build-and-test.yml)).

## 🐳 Docker Image

Docker images are published to [ghcr.io/realazthat/comfy-catapult][31] at each
tag.

```bash
# Use the published images at https://ghcr.io/realazthat/comfy-catapult.
docker run --rm --tty ghcr.io/realazthat/comfy-catapult:v2.2.0 --help

# /data in the docker image is the working directory, so paths are simpler.
docker run --rm --tty \
  -v "${PWD}:/data" \
  -e "COMFY_API_URL=${COMFY_API_URL}" \
  ghcr.io/realazthat/comfy-catapult:v2.2.0 \
  execute --workflow-path ./test_data/sdxlturbo_example_api.json
```

If you want to build the image yourself, you can use the Dockerfile in the
repository.

<!---->
```bash

# Build the docker image.
docker build -t my-comfy-catapult-image .

# Print usage.
docker run --rm --tty my-comfy-catapult-image --help

# /data in the docker image is the working directory, so paths are simpler.
docker run --rm --tty \
  -v "${PWD}:/data" \
  -e "COMFY_API_URL=${COMFY_API_URL}" \
  my-comfy-catapult-image \
  execute --workflow-path ./test_data/sdxlturbo_example_api.json

```
<!---->

## 🚸 Limitations

- Interrupting a job will interrupt any job, not the specific job interrupted.
  See [#5](https://github.com/realazthat/comfy-catapult/issues/5).

## TODO

- [ ] Helpers should support remote/cloud storage for ComfyUI input/output/model
      directories (Currently only supports local paths).
- [ ] ETA Estimator.
- [ ] Make sure the schema can parse the formats even if the format adds new
      fields.

## Contributions

### Development environment: Linux-like

- For running `pre.sh` (Linux-like environment).

  - From [./.github/dependencies.yml](./.github/dependencies.yml), which is used for
    the GH Action to do a fresh install of everything:

    ```yaml
    bash: scripts.
    findutils: scripts.
    grep: tests.
    xxd: tests.
    git: scripts, tests.
    xxhash: scripts (changeguard).
    rsync: out-of-directory test.
    jq: dependency for [yq](https://github.com/kislyuk/yq), which is used to generate
      the README; the README generator needs to use `tomlq` (which is a part of `yq`)
      to query `pyproject.toml`.
    
    ```

  - Requires `pyenv`, or an exact matching version of python as in
    [./.python-version](./.python-version).
  - `jq`, ([installation](https://jqlang.github.io/jq/)) required for
    [yq](https://github.com/kislyuk/yq), which is itself required for our
    `./README.md` generation, which uses `tomlq` (from the
    [yq](https://github.com/kislyuk/yq) package) to include version strings from
    [./pyproject.toml](./pyproject.toml).
  - act (to run the GH Action locally):
    - Requires nodejs.
    - Requires Go.
    - docker.
  - Generate animation:
    - docker
  - docker (for building the docker image).

### Commit Process

1. (Optionally) Fork the `develop` branch.
2. Stage your files: `git add path/to/file.py`.
3. `bash scripts/pre.sh`, this will format, lint, and test the code.
4. `git status` check if anything changed (generated `./README.md`
   for example), if so, `git add` the changes, and go back to the previous step.
5. `git commit -m "..."`.
6. Make a PR to `develop` (or push to develop if you have the rights).

## Release Process

These instructions are for maintainers of the project.

1. `develop` branch: Run `bash ./scripts/pre.sh` to ensure
   everything is in order.
2. `develop` branch: Bump the version in
   [./pyproject.toml](./pyproject.toml), following semantic versioning
   principles. Also modify the `last_release` and `last_stable_release` in the
   `[tool.comfy_catapult-project-metadata]` table as appropriate.
3. `develop` branch: Commit these changes with a message like "Prepare release
   X.Y.Z". (See the contributions section [above](#commit-process)).
4. `master` branch: Merge the `develop` branch into the `master` branch:
   `git checkout master && git merge develop --no-ff`.
5. `master` branch: Tag the release: Create a git tag for the release with
   `git tag -a vX.Y.Z -m "Version X.Y.Z"`.
6. Publish to PyPI: Publish the release to PyPI with
   `bash ./scripts/utilities/deploy-to-pypi.sh`.
7. Push to GitHub: Push the commit and tags to GitHub with `git push` and
   `git push --tags`.
8. `git checkout develop && git merge master` The `--no-ff` option adds a commit
   to the master branch for the merge, so refork the develop branch from the
   master branch.
9. `git push origin develop` Push the develop branch to GitHub.

[1]:
  https://img.shields.io/github/actions/workflow/status/realazthat/comfy-catapult/build-and-test.yml?branch=master&style=plastic
[2]:
  https://github.com/realazthat/comfy-catapult/actions/workflows/build-and-test.yml
[3]:
  https://img.shields.io/github/actions/workflow/status/realazthat/comfy-catapult/build-and-test.yml?branch=develop&style=plastic
[4]:
  https://github.com/realazthat/comfy-catapult/actions/workflows/build-and-test.yml
[5]: https://github.com/andreyryabtsev/comfyui-python-api
[6]: https://github.com/BennyKok/comfyui-deploy
[7]: https://github.com/pydn/ComfyUI-to-Python-Extension
[8]: https://github.com/Chaoses-Ib/ComfyScript
[9]: https://pypi.org/project/hordelib/
[10]: https://github.com/nathannlu/comfyui-cloud
[11]:
  https://img.shields.io/github/license/realazthat/comfy-catapult?style=plastic&color=0A1E1E
[12]:
  https://img.shields.io/pypi/v/comfy_catapult?style=plastic&color=0A1E1E
[13]: https://pypi.org/project/comfy_catapult/
[14]:
  https://img.shields.io/github/commits-since/realazthat/comfy-catapult/v2.2.0/master?style=plastic&color=0A1E1E
[15]:
  https://img.shields.io/github/commits-since/realazthat/comfy-catapult/v2.2.0/develop?style=plastic&color=0A1E1E
[16]:
  https://img.shields.io/github/last-commit/realazthat/comfy-catapult/master?style=plastic&color=0A1E1E
[17]:
  https://img.shields.io/github/last-commit/realazthat/comfy-catapult/develop?style=plastic&color=0A1E1E
[18]:
  https://img.shields.io/pypi/pyversions/comfy_catapult?style=plastic&color=0A1E1E
[19]:
  https://img.shields.io/github/languages/top/realazthat/comfy-catapult.svg?style=plastic&color=0A1E1E&cacheSeconds=28800
[20]:
  https://github.com/realazthat/comfy-catapult/compare/v2.2.0...master
[21]:
  https://github.com/realazthat/comfy-catapult/compare/v2.2.0...develop
[22]: https://github.com/piyushK52/comfy_runner
[23]: https://github.com/thecooltechguy/ComfyUI-ComfyRun
[24]: .github/logo-exported.svg
[25]:
  https://img.shields.io/badge/Audience-Developers-0A1E1E?style=plastic&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLXVzZXJzIj48cGF0aCBkPSJNMTYgMjF2LTJhNCA0IDAgMCAwLTQtNEg2YTQgNCAwIDAgMC00IDR2MiIvPjxjaXJjbGUgY3g9IjkiIGN5PSI3IiByPSI0Ii8+PHBhdGggZD0iTTIyIDIxdi0yYTQgNCAwIDAgMC0zLTMuODciLz48cGF0aCBkPSJNMTYgMy4xM2E0IDQgMCAwIDEgMCA3Ljc1Ii8+PC9zdmc+
[26]:
  https://img.shields.io/badge/Platform-Linux-0A1E1E?style=plastic&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLWxhcHRvcC1taW5pbWFsIj48cmVjdCB3aWR0aD0iMTgiIGhlaWdodD0iMTIiIHg9IjMiIHk9IjQiIHJ4PSIyIiByeT0iMiIvPjxsaW5lIHgxPSIyIiB4Mj0iMjIiIHkxPSIyMCIgeTI9IjIwIi8+PC9zdmc+
[27]: https://github.com/realazthat/comfy-catapult/tree/master
[28]: https://github.com/realazthat/comfy-catapult/tree/develop
[29]: https://github.com/city96/ComfyUI_NetDist
[30]: https://github.com/matan1905/ComfyUI-Serving-Toolkit
[31]: https://github.com/rvion/CushyStudio
[32]:
  https://github.com/comfyanonymous/ComfyUI/tree/89d0e9abeb31e44cccef46537cd10d8812130ef3/script_examples
  "Permalink"
