#!/bin/bash
# https://gist.github.com/mohanpedala/1e2ff5661761d3abd0385e8223e16425
set -e -x -v -u -o pipefail

# SNIPPETSTART
python -m comfy_catapult.cli \
    execute --workflow-path ./test_data/sdxlturbo_example_api.json
# SNIPPETEND
