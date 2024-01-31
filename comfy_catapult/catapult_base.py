# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import asyncio
import datetime
from abc import ABC, abstractmethod
from typing import List, NamedTuple, Sequence, Tuple

from anyio import Path

from comfy_catapult.comfy_schema import NodeID


class Progress(NamedTuple):
  value: int
  max_value: int


class JobStatus(NamedTuple):
  scheduled: datetime.datetime | None
  pending: datetime.datetime | None
  running: datetime.datetime | None
  success: datetime.datetime | None
  errored: datetime.datetime | None
  cancelled: datetime.datetime | None
  errors: List[Exception] = []
  job_history: dict | None = None

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
      important: Sequence[NodeID],
      job_debug_path: Path | None = None,
  ) -> dict:
    """Schedule a ComfyUI workflow job.

    Args:
        job_id (str): A unique identifier for the job.
        prepared_workflow (dict): Workflow to submit.
        important (List[NodeID]): List of important nodes (e.g output nodes we
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
                      job_id: str) -> Tuple[JobStatus, asyncio.Future[dict]]:
    raise NotImplementedError()

  @abstractmethod
  async def CancelJob(self, *, job_id: str):
    raise NotImplementedError()
