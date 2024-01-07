# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Catapult require contributions made to this file be licensed under the MIT
# license or a compatible open source license. See LICENSE.md for the license
# text.

from typing import Any, Dict, List, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, RootModel
from typing_extensions import Annotated

EXTRA = 'allow'

NodeID = Annotated[str, Field(alias='node_id')]
PromptID = Annotated[str, Field(alias='prompt_id')]
OutputName = Annotated[str, Field(alias='output_name')]
# This is BOOLEAN, INT etc.
OutputType = Annotated[str, Field(alias='output_type')]

# This is BOOLEAN, INT etc.
NamedInputType = Annotated[str, Field(alias='input_type')]
# This is a list of valid *values* for a combo input.
ComboInputType = Annotated[List[Any], Field(alias='combo_input_class')]


################################################################################
class APIWorkflowInConnection(NamedTuple):
  output_node_id: NodeID
  output_index: int


class APIWorkflowNodeMeta(BaseModel):
  model_config = ConfigDict(extra=EXTRA)
  title: str | None = None


class APIWorkflowNodeInfo(BaseModel):
  model_config = ConfigDict(populate_by_name=True, extra=EXTRA)

  inputs: Dict[str, str | int | float | bool | APIWorkflowInConnection | dict]
  class_type: str
  meta: APIWorkflowNodeMeta | None = Field(None, alias='_meta')

  # model_config = ConfigDict(populate_by_name=True)


class APIWorkflow(RootModel[Dict[NodeID, APIWorkflowNodeInfo]]):
  """This is the API format, you get it from `Save (API Format)` in the UI.


  See test_data/sdxlturbo_example_api.json for an example of this format in json.
  """
  root: Dict[NodeID, APIWorkflowNodeInfo]


################################################################################
class APISystemStatsSystem(BaseModel):
  model_config = ConfigDict(extra=EXTRA)

  os: str | None = None
  python_version: str | None = None
  embedded_python: bool | None = None


class APISystemStatsDevice(BaseModel):
  model_config = ConfigDict(extra=EXTRA)

  name: str | None = None
  type: str | None = None
  index: int | None = None
  vram_total: int | None = None
  vram_free: int | None = None
  torch_vram_total: int | None = None
  torch_vram_free: int | None = None


class APISystemStats(BaseModel):
  """Returned from /system_stats endpoint."""
  system: APISystemStatsSystem | None = None
  devices: List[APISystemStatsDevice] | None = None


################################################################################
class APIQueueInfoEntry(NamedTuple):
  number: int
  prompt_id: str
  prompt: APIWorkflow
  extra_data: dict
  outputs_to_execute: List[NodeID]


class APIQueueInfo(BaseModel):
  """Returned from /queue endpoint."""
  model_config = ConfigDict(extra='allow')

  queue_pending: List[APIQueueInfoEntry]
  queue_running: List[APIQueueInfoEntry]


################################################################################
class NodeErrorInfo(BaseModel):
  details: str
  extra_info: dict
  message: str
  type: str


class NodeErrors(BaseModel):
  class_type: str
  dependent_outputs: List[NodeID]
  errors: List[NodeErrorInfo]


class APIWorkflowTicket(BaseModel):
  """Return from post /prompt endpoint."""
  node_errors: Dict[NodeID, NodeErrors] | None = None
  number: int | None = None
  prompt_id: str | None = None
  error: str | None = None


################################################################################


class APIOutputUI(RootModel[Dict[OutputName, Any]]):
  root: Dict[OutputName, List[Any]]


class APIHistoryEntry(BaseModel):
  outputs: Dict[NodeID, APIOutputUI] | None = None
  prompt: APIQueueInfoEntry | None = None


class APIHistory(RootModel[Dict[PromptID, APIHistoryEntry]]):
  """Returned if you call /history and /history/{prompt_id} endpoints."""
  root: Dict[PromptID, APIHistoryEntry]


################################################################################

APIObjectKey = Annotated[str, Field(alias='object_key')]
"""
  Example:

  KSampler:
    input:
      required:
        model:
        - MODEL
    ...

  Here 'KSampler' is the APIObjectKey.

"""


class APIObjectInputInfo(BaseModel):
  """
  Example:

  seed:
  - INT
  - default: 0
    min: 0
    max: 18446744073709551615
  """
  # I allow extra here because I don't know what the keys are, and they seem to
  # vary quite a bit.
  model_config = ConfigDict(extra='allow')
  default: Any | None = None
  min: Any | None = None
  max: Any | None = None
  step: Any | None = None
  round: Any | None = None
  # Note: Everything else is going to be in the extra dict.


class APIObjectInputTuple(NamedTuple):
  """
  Example:

  seed:
  - INT
  - default: 0
    min: 0
    max: 18446744073709551615

    First item in the list/tuple is the type, second is the optional info.
  """
  type: NamedInputType | ComboInputType
  # For some reason, when type=='*', this is an empty string.
  info: APIObjectInputInfo | str | None = None


class APIObjectInput(BaseModel):
  """
  input:
      required:
        model:
        - MODEL
        seed:
        - INT
        - default: 0
          min: 0
          max: 18446744073709551615
        ...
  """
  model_config = ConfigDict(extra=EXTRA)

  required: Dict[str, APIObjectInputTuple | NamedInputType] | None = None
  """
  For some reason, when type=='*', it just shows the type without a
  `[type, {... limits}] tuple, so I allowed NamedInputType.
  """

  optional: Dict[str, APIObjectInputTuple | NamedInputType] | None = None
  hidden: Dict[str, APIObjectInputTuple | NamedInputType] | None = None


class APIObjectInfoEntry(BaseModel):
  """

  Example yaml version of this:

  input:
      required:
        model:
        - MODEL
        seed:
        - INT
        - default: 0
          min: 0
          max: 18446744073709551615
        ...
    output:
    - LATENT
    output_is_list:
    - false
    output_name:
    - LATENT
    name: KSampler
    display_name: KSampler
    description: ''
    category: sampling
    output_node: false
  """
  model_config = ConfigDict(extra=EXTRA)
  input: APIObjectInput
  output: OutputType | List[OutputType | List[OutputType]]
  output_is_list: List[bool]
  output_name: OutputName | List[OutputName]
  name: str
  display_name: str
  description: str
  category: str
  output_node: bool


class APIObjectInfo(RootModel[Dict[APIObjectKey, APIObjectInfoEntry]]):
  """Returned from /object_info endpoint.

  See test_data/object_info.yml for an example of this format in yaml.

  Example APIObjectInfo key and value, from test_data/object_info.yml:
  KSampler:
    input:
      required:
        model:
        - MODEL
        seed:
        - INT
        - default: 0
          min: 0
          max: 18446744073709551615
        steps:
        - INT
        - default: 20
          min: 1
          max: 10000
        cfg:
        - FLOAT
        - default: 8.0
          min: 0.0
          max: 100.0
          step: 0.1
          round: 0.01
        sampler_name:
        - - euler
          - euler_ancestral
          - heun
          - heunpp2
          - dpm_2
          - dpm_2_ancestral
          - lms
          - dpm_fast
          - dpm_adaptive
          - dpmpp_2s_ancestral
          - dpmpp_sde
          - dpmpp_sde_gpu
          - dpmpp_2m
          - dpmpp_2m_sde
          - dpmpp_2m_sde_gpu
          - dpmpp_3m_sde
          - dpmpp_3m_sde_gpu
          - ddpm
          - lcm
          - ddim
          - uni_pc
          - uni_pc_bh2
        scheduler:
        - - normal
          - karras
          - exponential
          - sgm_uniform
          - simple
          - ddim_uniform
        positive:
        - CONDITIONING
        negative:
        - CONDITIONING
        latent_image:
        - LATENT
        denoise:
        - FLOAT
        - default: 1.0
          min: 0.0
          max: 1.0
          step: 0.01
    output:
    - LATENT
    output_is_list:
    - false
    output_name:
    - LATENT
    name: KSampler
    display_name: KSampler
    description: ''
    category: sampling
    output_node: false
"""
  # model_config = ConfigDict(extra=EXTRA)

  root: Dict[APIObjectKey, APIObjectInfoEntry]


################################################################################
class APIUploadImageResp(BaseModel):
  name: str
  subfolder: str
  type: str


################################################################################
class WSExecutingData(BaseModel):
  """Websocket "executing" message.
  See:

  * https://github.com/comfyanonymous/ComfyUI/blob/61b3f15f8f2bc0822cb98eac48742fb32f6af396/server.py#L115
  * https://github.com/comfyanonymous/ComfyUI/blob/c782144433e41c21ae2dfd75d0bc28255d2e966d/main.py#L113
  * https://github.com/comfyanonymous/ComfyUI/blob/c782144433e41c21ae2dfd75d0bc28255d2e966d/execution.py#L146
  * https://github.com/comfyanonymous/ComfyUI/blob/e478b1794e91977c50dc6eea6228ef1248044507/script_examples/websockets_api_example.py#L36


  """
  model_config = ConfigDict(extra=EXTRA)
  node: str | None = None
  prompt_id: str | None = None


class WSMessage(BaseModel):
  """Messages from the websocket, if it is non-binary."""
  model_config = ConfigDict(extra=EXTRA)
  type: str
  data: dict


################################################################################
