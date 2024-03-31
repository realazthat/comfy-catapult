# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

from typing import Any, Dict, List, Literal, NamedTuple
from urllib.parse import urljoin

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator
from typing_extensions import Annotated

EXTRA = 'allow'

APINodeID = Annotated[
    str,
    Field(alias='node_id', description='The ID of a node in a workflow.')]
PromptID = Annotated[
    str,
    Field(
        alias='prompt_id',
        description=
        'The ID of a prompt (submission of a api workflow to the server to be executed). You can choose this yourself when submitting.'
    )]
ClientID = Annotated[str, Field(alias='client_id')]
OutputName = Annotated[
    str,
    Field(
        alias='output_name',
        description=
        'The name of an output in a node, in /history/, /history/{prompt_id} endpoints.'
    )]
# This is BOOLEAN, INT etc.
OutputType = Annotated[
    str,
    Field(
        alias='output_type',
        description=
        'The type of a named output of a node, in /object_info endpoint, and also can be seen/found in {node,custom node} implementations.'
    )]

# This is BOOLEAN, INT etc.
NamedInputType = Annotated[
    str,
    Field(
        alias='input_type',
        description=
        'The type of a named input of a node, in /object_info endpoint, and also can be seen/found in {node,custom node} implementations.'
    )]
# This is a list of valid *values* for a combo input.
ComboInputType = Annotated[List[Any], Field(alias='combo_input_class')]
ComfyFolderType = Literal['input', 'output', 'temp']
VALID_FOLDER_TYPES: List[ComfyFolderType] = ['input', 'output', 'temp']


################################################################################
class APIWorkflowInConnection(NamedTuple):
  """Represents a connection between two nodes in a workflow. This is used in the input of a node."""
  output_node_id: APINodeID
  output_index: int


class APIWorkflowNodeMeta(BaseModel):
  """Nodes are allowed to have a `_meta` field.

  The meta field was was added in
  https://github.com/comfyanonymous/ComfyUI/pull/2380 for information such as
  the title of the node.
  """
  model_config = ConfigDict(extra=EXTRA)
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """
  title: str | None = None


class APIWorkflowNodeInfo(BaseModel):
  model_config = ConfigDict(populate_by_name=True, extra=EXTRA)
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  populate_by_name: This is to allow `meta` field to be populated by `_meta` or
  `meta`.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """

  inputs: Dict[str, str | int | float | bool | APIWorkflowInConnection | dict]
  class_type: str
  meta: APIWorkflowNodeMeta | None = Field(None, alias='_meta')


class APIWorkflow(RootModel[Dict[APINodeID, APIWorkflowNodeInfo]]):
  """This is the API format, you get it from `Save (API Format)` in the UI.


  See test_data/sdxlturbo_example_api.json for an example of this format in json.
  """
  root: Dict[APINodeID, APIWorkflowNodeInfo]


################################################################################
class APISystemStatsSystem(BaseModel):
  model_config = ConfigDict(extra=EXTRA)
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """

  os: str | None = None
  python_version: str | None = None
  embedded_python: bool | None = None


class APISystemStatsDevice(BaseModel):
  model_config = ConfigDict(extra=EXTRA)
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """
  name: str | None = None
  type: str | None = None
  index: int | None = None
  vram_total: int | None = None
  vram_free: int | None = None
  torch_vram_total: int | None = None
  torch_vram_free: int | None = None


class APISystemStats(BaseModel):
  """Returned from /system_stats endpoint."""
  model_config = ConfigDict(extra=EXTRA)
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """
  system: APISystemStatsSystem | None = None
  devices: List[APISystemStatsDevice] | None = None


################################################################################
class APIQueueInfoEntry(NamedTuple):
  number: int
  prompt_id: PromptID
  prompt: APIWorkflow
  extra_data: dict
  outputs_to_execute: List[APINodeID]


class APIQueueInfo(BaseModel):
  """Returned from /queue endpoint."""
  model_config = ConfigDict(extra=EXTRA)
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """

  queue_pending: List[APIQueueInfoEntry]
  queue_running: List[APIQueueInfoEntry]


################################################################################
class NodeErrorInfo(BaseModel):
  model_config = ConfigDict(extra=EXTRA)
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """
  details: str
  extra_info: dict
  message: str
  type: str


class NodeErrors(BaseModel):
  model_config = ConfigDict(extra=EXTRA)
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """
  class_type: str
  dependent_outputs: List[APINodeID]
  errors: List[NodeErrorInfo]


class APIWorkflowTicket(BaseModel):
  """Return from post /prompt endpoint."""
  model_config = ConfigDict(extra=EXTRA)
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """
  node_errors: Dict[APINodeID, NodeErrors] | None = None
  number: int | None = None
  prompt_id: PromptID | None = None
  error: str | None = None


################################################################################


class APIOutputUI(RootModel[Dict[OutputName, List[Any]]]):
  root: Dict[OutputName, List[Any]]


class APIHistoryEntryStatusNote(NamedTuple):
  name: str
  data: Any


class APIHistoryEntryStatus(BaseModel):
  """

  Example:
    "status": {
      "status_str": "success",
      "completed": true,
      "messages": [
        [
          "execution_start",
          { "prompt_id": "b1b64df6-9b2c-4a09-bd0e-b6c294702085" }
        ],
        [
          "execution_cached",
          { "nodes": [], "prompt_id": "b1b64df6-9b2c-4a09-bd0e-b6c294702085" }
        ]
      ]
    }
  """
  model_config = ConfigDict(extra=EXTRA)
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """
  status_str: str | None = None
  completed: bool | None = None
  messages: List[APIHistoryEntryStatusNote] | None = None


class APIHistoryEntry(BaseModel):
  model_config = ConfigDict(extra=EXTRA)
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """
  outputs: Dict[APINodeID, APIOutputUI] | None = None
  prompt: APIQueueInfoEntry | None = None
  status: APIHistoryEntryStatus | None = None


class APIHistory(RootModel[Dict[PromptID, APIHistoryEntry]]):
  """Returned if you call /history and /history/{prompt_id} endpoints.

  TODO: Show an example.
  """
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
  model_config = ConfigDict(extra=EXTRA)
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.

  I allow extra here because I don't know what the keys are, and they seem to
  vary quite a bit.
  """
  default: Any | None = None
  min: Any | None = None
  max: Any | None = None
  step: Any | None = None
  round: Any | None = None
  # Note: Everything else is going to be in the extra dict. Access it with the
  # `extra` attribute.


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
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """

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
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """
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
  type: ComfyFolderType


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
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """
  node: str | None = None
  prompt_id: PromptID | None = None


class WSMessage(BaseModel):
  """Messages from the websocket, if it is non-binary."""
  model_config = ConfigDict(extra=EXTRA)
  """This is a pydantic thing, to configure the model, it is not an accessible field.

  extra: This is just to future proof the schema so it won't break if extra
  fields are added. They'll be stored dynamically.
  """
  type: str
  data: dict


################################################################################


class ComfyUIPathTriplet(BaseModel):
  """
  Represents a folder_type/subfolder/filename triplet, which ComfyUI API and
  some nodes use as file paths.
  """
  model_config = ConfigDict(frozen=True)

  type: ComfyFolderType
  subfolder: str
  filename: str

  @field_validator('type')
  @classmethod
  def validate_folder_type(cls, v: str):
    if v not in VALID_FOLDER_TYPES:
      raise ValueError(
          f'folder_type {repr(v)} is not one of {VALID_FOLDER_TYPES}')
    return v

  @field_validator('subfolder')
  @classmethod
  def validate_subfolder(cls, v: str):
    if v.startswith('/'):
      raise ValueError(f'subfolder {repr(v)} must not start with a slash')
    return v

  @field_validator('filename')
  @classmethod
  def validate_filename(cls, v: str):
    if '/' in v:
      raise ValueError(f'filename {repr(v)} must not contain a slash')
    if v == '':
      raise ValueError(f'filename {repr(v)} must not be empty')
    return v

  def ToLocalPathStr(self, *, include_folder_type: bool) -> str:
    """Converts this triplet to something like `input/subfolder/filename`.
    """
    subfolder = self.subfolder
    if subfolder == '':
      subfolder = '.'
    if not subfolder.endswith('/'):
      subfolder += '/'

    local_path = urljoin(subfolder, self.filename)
    if include_folder_type:
      local_path = urljoin(f'{self.type}/', local_path)
    return local_path
