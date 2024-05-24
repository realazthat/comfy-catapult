# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import asyncio
import datetime
from abc import ABC, abstractmethod
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from anyio import Path

from .comfy_schema import APINodeID


class Progress(NamedTuple):
  value: int
  max_value: int


class ExceptionInfo(NamedTuple):
  type: str
  message: str
  traceback: str
  attributes: Dict[str, str]


class JobStatus(NamedTuple):

  scheduled: Optional[datetime.datetime]
  pending: Optional[datetime.datetime]
  running: Optional[datetime.datetime]
  success: Optional[datetime.datetime]
  errored: Optional[datetime.datetime]
  cancelled: Optional[datetime.datetime]
  errors: List[ExceptionInfo]
  job_history: Optional[dict] = None

  def IsDone(self) -> bool:
    return (self.success is not None or self.errored is not None
            or self.cancelled is not None)


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

  @abstractmethod
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
    raise NotImplementedError()

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
