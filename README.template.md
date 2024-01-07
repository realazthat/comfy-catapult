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

The following assumes you are running in a bash-like environment, getting these
to work in Windows is left as an exercise for the reader.

### Example workflow: Prepare ComfyUI

You need to get `sd_xl_turbo_1.0_fp16.safetensors` into the ComfyUI model
directory.

Hugging Face page:
[huggingface.co/stabilityai/sdxl-turbo/blob/main/sd_xl_turbo_1.0_fp16.safetensors](https://huggingface.co/stabilityai/sdxl-turbo/blob/main/sd_xl_turbo_1.0_fp16.safetensors).

Direct download link:
[huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors](huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors).

### Download the example workflow, and export it in the API format

```bash
# Download the workflow:
wget https://github.com/comfyanonymous/ComfyUI_examples/raw/master/sdturbo/sdxlturbo_example.png

# Open the Workflow in ComfyUI, and export it in the API format to
# `./sdxlturbo_example_api.json`.

# Or just use `test_data/sdxlturbo_example_api.json`.

# Optional: You might want to examine the json file just to see the shape of the
# nodes, what they are called, what their inputs and outputs are called, and what
# their default values are, etc.
```

### Install as a library from git and run the examples

```bash
# Inside your environment:
pip install https://github.com/realazthat/comfy-catapult.git
# Or
git clone https://github.com/realazthat/comfy-catapult.git
pip install .



# If you set this environment variable, you don't have to specify it as an
# argument.
export COMFY_API_URL=http://127.0.0.1:8188
# Note, in WSL2 you may have to use the following if ComfyUI is running on the
# Windows side:
export COMFY_API_URL=http://host.docker.internal:8188


python -m comfy_catapult.examples.sdxlturbo_example_catapulter \
  --api_workflow_json_path "$PWD/sdxlturbo_example_api.json"
  --tmp_path "$PWD/.deleteme/tmp/" \
  --output_path "$PWD/.deleteme/output.png" \
  --positive_prompt "amazing cloudscape, towering clouds, thunderstorm, awe" \
  --negative_prompt "dull, blurry, nsfw"

# Now $PWD/.deleteme/output.png should contain the output image.

python -m comfy_catapult.examples.simple_example_catapult
python -m comfy_catapult.examples.sdxlturbo_example_easy_catapult

# Optional arguments:
#   --comfy_api_url "..."


# Examine comfy_catapult/examples/sdxlturbo_example_catapulter.py to see how to
# use the library.
```

### Install dependencies and run the examples

```bash
# Install dependencies:
pip install -r requirements.txt



# Run the workflow:
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
{% include 'comfy_catapult/examples/sdxlturbo_example_catapulter.py' %}
```

### Parsing the API format into the Pydantic models schema for easier navigation

From `comfy_catapult/examples/using_pydantic.py`:

```py
{% include 'comfy_catapult/examples/add_a_node.py' %}
```

### Adding a new node to a workflow

From `comfy_catapult/examples/add_a_node.py`:

```py
{% include 'comfy_catapult/examples/add_a_node.py' %}
```

## Known to work on:

- **Python 3.11.4**, WSL2/Windows11, Ubuntu 22.04.2 LTS

## Limitations

- ETA estimator isn't working

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
