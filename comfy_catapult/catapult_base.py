# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import asyncio
import datetime
from abc import ABC, abstractmethod
from typing import (Dict, List, Literal, NamedTuple, Optional, Sequence, Tuple,
                    Union, overload)

from anyio import Path
from pydantic import BaseModel, ConfigDict, Field

from .comfy_schema import APINodeID, APIWorkflowTicket


class Progress(NamedTuple):
  value: int
  max_value: int


class ExceptionInfo(NamedTuple):
  type: str
  message: str
  traceback: str
  attributes: Dict[str, str]


class JobStatus(BaseModel):
  model_config = ConfigDict(frozen=True)

  scheduled: Optional[datetime.datetime] = Field(
      ..., description='Time the job was scheduled with Comfy Catapult.')
  comfy_scheduled: Optional[datetime.datetime] = Field(
      ..., description='Time the job was scheduled with ComfyUI.')
  pending: Optional[datetime.datetime] = Field(
      ...,
      description='If/when the job is seen in the ComfyUI /queue as pending.')
  running: Optional[datetime.datetime] = Field(
      ...,
      description='If/when the job is seen in the ComfyUI /queue as running.')
  success: Optional[datetime.datetime] = Field(
      ...,
      description=
      'If/when the job is seen in the ComfyUI /history as successful.')
  errored: Optional[datetime.datetime] = Field(
      ...,
      description='If/when the job has encountered an unrecoverable error.')
  cancelled: Optional[datetime.datetime] = Field(
      ..., description='If/when the job was cancelled.')
  errors: List[ExceptionInfo]

  system_stats_check: Optional[datetime.datetime] = Field(
      None,
      description=
      'Last time system stats were successfully checked (while this job is not done).'
  )
  queue_check: Optional[datetime.datetime] = Field(
      None,
      description=
      'Last time /queue/job_id was successfully checked for (while this job is not done).'
  )

  ticket: Optional[APIWorkflowTicket] = Field(
      ..., description='The ticket returned from the ComfyUI API.')

  job_history: Optional[dict] = Field(
      None,
      description=
      'The history of the job. This is only set when the job is done and the history is successfully retrieved.'
  )

  def IsDone(self) -> bool:
    """Returns True if the job is no longer viable; either it finished or an error occurred etc.."""
    return (self.success is not None or self.errored is not None
            or self.cancelled is not None)

  def _replace(self, **kwargs):
    return self.copy(update=kwargs)


class ComfyCatapultBase(ABC):

  @abstractmethod
  def __init__(self):
    pass

  @abstractmethod
  async def __aenter__(self):
    raise NotImplementedError()

  @abstractmethod
  async def __aexit__(self, exc_type, exc, tb):
    raise NotImplementedError()

  @abstractmethod
  async def Close(self):
    raise NotImplementedError()

  @overload
  @abstractmethod
  async def Catapult(
      self,
      *,
      job_id: str,
      prepared_workflow: dict,
      important: Sequence[APINodeID],
      use_future_api: Literal[True],
      job_debug_path: Optional[Path] = None
  ) -> Tuple[JobStatus, 'asyncio.Future[dict]']:
    ...

  @overload
  @abstractmethod
  async def Catapult(self,
                     *,
                     job_id: str,
                     prepared_workflow: dict,
                     important: Sequence[APINodeID],
                     use_future_api: Literal[False] = False,
                     job_debug_path: Optional[Path] = None) -> dict:
    ...

  @abstractmethod
  async def Catapult(
      self,
      *,
      job_id: str,
      prepared_workflow: dict,
      important: Sequence[APINodeID],
      use_future_api: bool = False,
      job_debug_path: Optional[Path] = None
  ) -> Union[dict, Tuple[JobStatus, 'asyncio.Future[dict]']]:
    """Schedule a ComfyUI workflow job.

    Args:
        job_id (str): A unique identifier for the job. Note: This string must
          be unique, and must be slugified! Use python-slugify to slugify the
          string. Note: This is not the same string as the prompt_id returned
          from ComfyUI API. You can find that in the JobStatus.ticket returned
          from GetStatus().
        prepared_workflow (dict): Workflow to submit.
        important (List[APINodeID]): List of important nodes (e.g output nodes
          we are interested in).
        use_future_api (bool): Use the future API; returns a future that will
          resolve to the job history when the job is done.
        job_debug_path (Path, optional): Path to save debug information. If
          None, will use sensible defaults.

    Raises:
        WorkflowSubmissionError: Failed to submit workflow.

    Returns:
        Union[dict, Tuple[JobStatus, asyncio.Future[dict]]]: If use_future_api
        is True, returns a tuple of the job status and a future that will
        resolve to the job history when the job is done. Otherwise, returns the
        job history.
    """
    raise NotImplementedError()

  @abstractmethod
  async def GetStatus(self, *,
                      job_id: str) -> 'Tuple[JobStatus, asyncio.Future[dict]]':
    """Get the status of a job.

    Args:
        job_id (str): The job id.

    Returns:
        Tuple[JobStatus, asyncio.Future[dict]]: The status of the job, and a
          future that will resolve to the job history when the job is done.
    """

  @abstractmethod
  async def GetExceptions(self, *, job_id: str) -> List[Exception]:
    """List of exceptions that occurred during the job.

    Args:
        job_id (str): The job id.

    Returns:
        List[Exception]: List of exceptions that occurred during the job.
    """
    raise NotImplementedError()

  @abstractmethod
  async def CancelJob(self, *, job_id: str):
    """Cancel a job. No-op if the job is done. Will also try to cancel the job remotely.

    Args:
        job_id (str): The job id.
    """
    raise NotImplementedError()
