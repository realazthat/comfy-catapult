# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project require contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import asyncio
import datetime
import enum
import json
import sys
import textwrap
import threading
import traceback
import uuid
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, Generic, List, Sequence, Tuple, TypeVar
from urllib.parse import ParseResult, urlparse, urlunparse

import aiofiles
from anyio import Path
from slugify import slugify
from websockets import WebSocketClientProtocol, connect

from comfy_catapult.api_client import ComfyAPIClientBase, YamlDump
from comfy_catapult.catapult_base import ComfyCatapultBase, JobStatus, Progress
from comfy_catapult.comfy_schema import (APIHistory, APIHistoryEntry,
                                         APIQueueInfo, APISystemStats,
                                         APIWorkflowTicket, NodeID, WSMessage)
from comfy_catapult.comfy_utils import TryParseAsModel
from comfy_catapult.errors import NodesNotExecuted, WorkflowSubmissionError


@dataclass
class _Job:

  class RemoteStatus(enum.Enum):
    NONE = enum.auto()
    PENDING_OR_RUNNING = enum.auto()

  job_id: str
  prepared_workflow: dict
  important_nodes: Tuple[NodeID, ...]
  ticket: APIWorkflowTicket
  status: JobStatus
  future: asyncio.Future[dict]
  remote_job_status: RemoteStatus


T = TypeVar('T')


@dataclass
class _Guess(Generic[T]):
  value: T | None
  updated: datetime.datetime


class ComfyCatapult(ComfyCatapultBase):

  def __init__(self, *, comfy_client: ComfyAPIClientBase,
               debug_path: Path | None):

    self._comfy_client = comfy_client
    ############################################################################
    self._client_id = str(uuid.uuid4())

    # self._lock = _DummyLock()
    self._lock = asyncio.Lock()
    self._stop_event = threading.Event()

    self._jobs: Dict[str, _Job] = {}
    # {ticket.prompt_id -> job_id}
    self._prompt_id_index: Dict[str, str] = {}

    self._monitoring_task: asyncio.Task[None] = asyncio.create_task(
        self._MonitoringThread())
    self._monitoring_task.get_loop().set_debug(True)
    self._poll_task: asyncio.Task[None] = asyncio.create_task(self._PollLoop())
    self._guess_currently_running_job_id: _Guess[str] = _Guess(
        value=None, updated=self._Now())
    self._guess_currently_running_node_id: _Guess[str] = _Guess(
        value=None, updated=self._Now())
    self._guess_currently_running_node_progress: _Guess[Progress] = _Guess(
        value=None, updated=self._Now())

    # Reconnect to the webscoket every 20 seconds, because the currently running
    # node is sent upon reconnect.
    self._ws_connect_interval = 20.
    self._debug_path = debug_path

  async def __aenter__(self):
    await self._comfy_client.__aenter__()
    return self

  async def __aexit__(self, exc_type, exc_value, traceback):
    await self.Close()

  async def Close(self):

    self._stop_event.set()

    for job in self._jobs.values():
      job.future.cancel()
    await self._CheckError()
    self._monitoring_task.cancel()
    self._poll_task.cancel()
    try:
      await self._monitoring_task
    except asyncio.CancelledError:
      pass
    try:
      await self._poll_task
    except asyncio.CancelledError:
      pass

  async def Catapult(
      self,
      *,
      job_id: str,
      prepared_workflow: dict,
      important: Sequence[NodeID],
  ) -> dict:
    assert job_id not in self._jobs, f'User job id {job_id} already exists'
    assert slugify(job_id) == job_id, f'User job id {job_id} is not slugified'

    print('self._client.PostPrompt()', file=sys.stderr)

    ticket: APIWorkflowTicket = await self._comfy_client.PostPrompt(
        prompt_workflow=prepared_workflow)
    print('self._client.PostPrompt(), done', file=sys.stderr)

    has_errors = False
    if ticket.node_errors is not None and len(ticket.node_errors) > 0:
      has_errors = True
    if ticket.error is not None:
      has_errors = True
    if ticket.prompt_id is None:
      has_errors = True

    if has_errors:
      raise WorkflowSubmissionError(
          f'Errors in workflow'
          f'\nprepared_workflow:\n{textwrap.indent(YamlDump(prepared_workflow), prefix="  ")}'
          f'\nticket:\n{textwrap.indent(YamlDump(ticket.model_dump()), prefix="  ")}',
          prepared_workflow=deepcopy(prepared_workflow),
          ticket=ticket)

    assert ticket.prompt_id is not None

    async with self._lock:
      self._prompt_id_index[ticket.prompt_id] = job_id
      self._jobs[job_id] = _Job(
          job_id=job_id,
          prepared_workflow=prepared_workflow,
          important_nodes=tuple(important),
          ticket=ticket,
          status=JobStatus(scheduled=self._Now(),
                           running=None,
                           pending=None,
                           success=None,
                           errored=None,
                           cancelled=None),
          remote_job_status=_Job.RemoteStatus.PENDING_OR_RUNNING,
          future=asyncio.Future())
      job = self._jobs[job_id]
    return await job.future

  async def GetStatus(self, *,
                      job_id: str) -> Tuple[JobStatus, asyncio.Future[dict]]:
    async with self._lock:
      if job_id not in self._jobs:
        raise KeyError(f'Job id {job_id} not found')
      job = self._jobs[job_id]
      return deepcopy(job.status), job.future

  async def CancelJob(self, *, job_id: str):
    async with _JobContext(job_id=job_id, comfy=self):
      async with self._lock:
        prompt_id = self._jobs[job_id].ticket.prompt_id
        remote_job_status = self._jobs[job_id].remote_job_status

      if remote_job_status == _Job.RemoteStatus.PENDING_OR_RUNNING \
          and prompt_id is not None:
        # TODO(realazthat/comfy-catapult#5): We don't know for sure that the
        # current job is the one we're cancelling, as there could be a race
        # condition here.
        await self._comfy_client.PostInterrupt()
        await self._comfy_client.PostQueue(delete=[prompt_id], clear=False)

        async with self._lock:
          self._jobs[job_id].remote_job_status = _Job.RemoteStatus.NONE

      now = self._Now()
      async with self._lock:
        job = self._jobs[job_id]
        if not job.status.IsDone():
          job.status = job.status._replace(cancelled=now)
          job.future.cancel()

  async def _ReceivedJobHistory(self, *, job_id: str, history: APIHistory):
    async with _JobContext(job_id=job_id, comfy=self):
      assert isinstance(history, APIHistory)

      async with self._lock:
        prepared_workflow: dict = deepcopy(self._jobs[job_id].prepared_workflow)
        prompt_id = self._jobs[job_id].ticket.prompt_id
        important_nodes = deepcopy(self._jobs[job_id].important_nodes)

      if len(history.root) == 0:
        return
      assert prompt_id in history.root
      job_history: APIHistoryEntry = history.root[prompt_id]
      async with self._lock:
        self._jobs[job_id].status = self._jobs[job_id].status._replace(
            job_history=job_history)

      extra_data: dict | None = None
      outputs_to_execute: List[NodeID] = []
      outputs_with_data: List[NodeID] = []
      if job_history.outputs is not None:
        outputs_with_data = list(job_history.outputs.keys())
      if job_history.prompt is not None:
        if job_history.prompt.extra_data is not None:
          extra_data = job_history.prompt.extra_data
        if job_history.prompt.outputs_to_execute is not None:
          outputs_to_execute = job_history.prompt.outputs_to_execute

      print('job_history.prompt.extra_data.model_dump():', file=sys.stderr)
      print(YamlDump(extra_data), file=sys.stderr)

      print('job_history.prompt.outputs_to_execute.model_dump():',
            file=sys.stderr)
      print(YamlDump(outputs_to_execute), file=sys.stderr)

      print('outputs_to_execute:', file=sys.stderr)
      print(YamlDump(outputs_to_execute), file=sys.stderr)
      print('outputs_that_executed:', file=sys.stderr)
      print(YamlDump(outputs_with_data), file=sys.stderr)

      bad_dataless_outputs = [
          node_id for node_id in outputs_to_execute
          if node_id not in outputs_with_data
      ]

      def _GetTitles(node_ids: List[NodeID]) -> List[str | None]:
        titles = []
        for node_id in node_ids:
          node_info: dict = prepared_workflow.get(node_id, {})
          meta: dict = node_info.get('_meta', {})
          title: str | None = meta.get('title', None)
          titles.append(title)
        return titles

      if len(bad_dataless_outputs) > 0:
        print('bad_dataless_outputs:', file=sys.stderr)
        print(YamlDump(bad_dataless_outputs), file=sys.stderr)
        print('_GetTitles(bad_dataless_outputs):', file=sys.stderr)
        print(YamlDump(_GetTitles(bad_dataless_outputs)), file=sys.stderr)

      dataless_important_outputs = [
          node_id for node_id in bad_dataless_outputs
          if node_id in important_nodes
      ]
      if len(dataless_important_outputs) > 0:
        print('dataless_important_outputs:', file=sys.stderr)
        print(YamlDump(dataless_important_outputs), file=sys.stderr)
        print('_GetTitles(dataless_important_outputs):', file=sys.stderr)
        print(YamlDump(_GetTitles(dataless_important_outputs)), file=sys.stderr)
        raise NodesNotExecuted(nodes=list(dataless_important_outputs),
                               titles=_GetTitles(dataless_important_outputs))

      # await self._eta_estimator.RecordFinished(job_id=job_id)

      now = self._Now()
      async with self._lock:
        job = self._jobs[job_id]
        job.future.set_result(job_history.model_dump())
        job.status = job.status._replace(success=now)

  async def _Poll(self):
    # TODO: Use locks properly in this function

    ############################################################################
    await self._CheckError()
    ############################################################################
    # Make sure any hanging future that is done matches the job status.
    done_futures_jobs: List[str] = []
    async with self._lock:
      for job_id, job in self._jobs.items():
        if job.future.done() and not job.status.IsDone():
          done_futures_jobs.append(job_id)
    for job_id in done_futures_jobs:
      async with _JobContext(job_id=job_id, comfy=self):
        async with self._lock:
          job = self._jobs[job_id]
          # See if an error occurred.
          job.future.result()
          job.status = job.status._replace(success=self._Now())
    ############################################################################
    system_stats: APISystemStats = await self._comfy_client.GetSystemStats()
    print(YamlDump(system_stats.model_dump()), file=sys.stderr)
    ############################################################################
    queue_info: APIQueueInfo = await self._comfy_client.GetQueue()

    prompt_id_2_status: Dict[str, str] = {}
    for pending in queue_info.queue_running:
      prompt_id_2_status[pending.prompt_id] = 'running'
    for running in queue_info.queue_pending:
      prompt_id_2_status[running.prompt_id] = 'pending'
    pending_count = sum(
        [1 for status in prompt_id_2_status.values() if status == 'pending'],
        start=0)
    running_count = sum(
        [1 for status in prompt_id_2_status.values() if status == 'running'],
        start=0)

    print('pending_count:', pending_count, file=sys.stderr)
    print('running_count:', running_count, file=sys.stderr)

    for prompt_id, status in prompt_id_2_status.items():
      async with self._lock:
        job_id = self._prompt_id_index.get(prompt_id, None)
        if job_id is None:
          continue
        job: _Job = self._jobs[job_id]

        if status == 'pending' and job.status.pending is None:
          job.status = job.status._replace(pending=self._Now())

        if status == 'running' and job.status.running is None:
          job.status = job.status._replace(running=self._Now())
          self._guess_currently_running_job_id = _Guess(value=job_id,
                                                        updated=self._Now())
          self._guess_currently_running_node_id = _Guess(value=None,
                                                         updated=self._Now())
          self._guess_currently_running_node_progress = _Guess(
              value=None, updated=self._Now())

    # print('self._jobs:', file=sys.stderr)
    # pprint(self._jobs, indent=2, stream=sys.stderr)

    ############################################################################
    prompt_info = await self._comfy_client.GetPromptRaw()
    assert isinstance(prompt_info, dict)

    exec_info = prompt_info['exec_info']
    queue_remaining = exec_info['queue_remaining']
    assert isinstance(queue_remaining, int)
    print('queue_remaining:', queue_remaining, file=sys.stderr)
    ############################################################################
    # Check the /history endpoint to see if there are any updates on our jobs.
    async with self._lock:
      job_ids = list(self._jobs.keys())

    # Update job.remote_job_status.
    for job_id in job_ids:
      async with self._lock:
        new_remote_job_status = (_Job.RemoteStatus.NONE
                                 if job_id not in prompt_id_2_status else
                                 _Job.RemoteStatus.PENDING_OR_RUNNING)
        self._jobs[job_id].remote_job_status = new_remote_job_status

    # Update job.job_history.
    for job_id in job_ids:
      async with self._lock:
        if job_id in prompt_id_2_status:
          # In this case, it's pending or running, not going to be in the
          # `/history` endpoint.
          continue

        if self._jobs[job_id].status.job_history is not None:
          # We already have the job history.
          continue
        prompt_id = self._jobs[job_id].ticket.prompt_id
        if prompt_id is None:
          # This should never happen, but :shrug:.
          continue

      ##########################################################################
      history: APIHistory = (await
                             self._comfy_client.GetHistory(prompt_id=prompt_id))

      await self._ReceivedJobHistory(job_id=job_id, history=history)
      ##########################################################################

  def _Now(self) -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)

  async def _Record(self):
    async with self._lock:
      guess_currently_running_job_id = self._guess_currently_running_job_id
      # guess_currently_running_node_id = self._guess_currently_running_node_id
      # guess_currently_running_node_progress = self._guess_currently_running_node_progress

    if guess_currently_running_job_id.value is not None:
      pass

  async def _LoopWS(self, *, ws: WebSocketClientProtocol):
    while True:
      try:
        print('websocket recv', file=sys.stderr)
        out = await ws.recv()
        if not isinstance(out, str):
          print('websocket type(out):', type(out), file=sys.stderr)
          continue
        print('websocket raw:', file=sys.stderr)
        print(YamlDump(out), file=sys.stderr)
        message = await TryParseAsModel(content=json.loads(out),
                                        model_type=WSMessage)
        print('websocket message:', file=sys.stderr)
        print(YamlDump(message.__dict__), file=sys.stderr)

        if message.type == 'executing' and 'last_node_id' in message.data:
          last_node_id = message.data['last_node_id']

          self._guess_currently_running_node_id = _Guess(value=last_node_id,
                                                         updated=self._Now())
          await self._Record()
        elif message.type == 'executing' and 'node' in message.data and 'prompt_id' in message.data:
          prompt_id = message.data.get('prompt_id', None)
          node_id: str | None = message.data.get('node', None)
          async with self._lock:
            job_id = self._prompt_id_index.get(
                prompt_id, None) if prompt_id is not None else None
            if job_id is not None:
              job = self._jobs[job_id]
              if job.status.running is None:
                job.status = job.status._replace(running=self._Now())
            self._guess_currently_running_job_id = _Guess(value=job_id,
                                                          updated=self._Now())
            self._guess_currently_running_node_id = _Guess(value=node_id,
                                                           updated=self._Now())
            self._guess_currently_running_node_progress = _Guess(
                value=None, updated=self._Now())
          await self._Record()
        elif message.type == 'execution_start' and 'prompt_id' in message.data:
          prompt_id = message.data['prompt_id']
          async with self._lock:
            job_id = self._prompt_id_index.get(
                prompt_id, None) if prompt_id is not None else None
            if job_id is not None:
              job = self._jobs[job_id]
              if job.status.running is None:
                job.status = job.status._replace(running=self._Now())
            self._guess_currently_running_job_id = _Guess(value=job_id,
                                                          updated=self._Now())
            self._guess_currently_running_node_id = _Guess(value=None,
                                                           updated=self._Now())
            self._guess_currently_running_node_progress = _Guess(
                value=None, updated=self._Now())
          await self._Record()

        elif message.type == 'executed' and 'node' in message.data and 'output_ui' in message.data and 'prompt_id' in message.data:
          # Finished a single node?
          prompt_id: str | None = message.data.get('prompt_id', None)
          node_id: str | None = message.data.get('node', None)
          # output_ui = message.data['output_ui']
          async with self._lock:
            job_id = self._prompt_id_index.get(
                prompt_id, None) if prompt_id is not None else None
            if job_id is not None:
              job = self._jobs[job_id]
              if job.status.running is None:
                job.status = job.status._replace(running=self._Now())
            else:
              node_id = None

            self._guess_currently_running_job_id = _Guess(value=job_id,
                                                          updated=self._Now())
            self._guess_currently_running_node_id = _Guess(value=node_id,
                                                           updated=self._Now())
            self._guess_currently_running_node_progress = _Guess(
                value=None, updated=self._Now())
          await self._Record()
        elif message.type in ['execution_interrupted', 'execution_error']:
          prompt_id: str | None = message.data.get('prompt_id', None)
          node_id: str | None = message.data.get('node_id', None)
          node_type: str | None = message.data.get('node_type', None)
          # executed: list | None = message.data.get('executed', None)
          async with self._lock:
            job_id = self._prompt_id_index.get(
                prompt_id, None) if prompt_id is not None else None
            if job_id is not None:
              job = self._jobs[job_id]
              if not job.status.IsDone():
                now = self._Now()
                job.status = job.status._replace(
                    errored=now,
                    errors=job.status.errors + [
                        Exception(
                            f'Node {node_id} of type {node_type} errored: {message.data}'
                        )
                    ])
            self._guess_currently_running_job_id = _Guess(value=None,
                                                          updated=self._Now())
            self._guess_currently_running_node_id = _Guess(value=None,
                                                           updated=self._Now())
            self._guess_currently_running_node_progress = _Guess(
                value=None, updated=self._Now())
          await self._Record()
        elif message.type == 'progress':
          value = message.data.get('value', None)
          max_value = message.data.get('max_value', None)
          if isinstance(value, int) and isinstance(max_value, int):
            async with self._lock:
              self._guess_currently_running_node_progress = _Guess(
                  value=Progress(value=value, max_value=max_value),
                  updated=self._Now())
            await self._Record()
      except asyncio.CancelledError:
        raise
      except Exception:
        traceback.print_exc(file=sys.stderr)

  async def _PollLoop(self):
    while not self._stop_event.is_set():
      try:
        await asyncio.sleep(5)
        await self._Poll()
      except asyncio.CancelledError:
        raise
      except Exception:
        traceback.print_exc(file=sys.stderr)

  async def _MonitoringThread(self):

    async with self._lock:
      client_id = self._client_id
      comfy_api_url: str = self._comfy_client.GetURL()
      ws_connect_interval: float = self._ws_connect_interval

    # replace protocol with ws, using a url library
    ws_url: ParseResult = urlparse(comfy_api_url)
    ws_url = ws_url._replace(scheme='ws')
    ws_url = ws_url._replace(path='/ws')
    ws_url = ws_url._replace(query=f'clientId={client_id}')

    async def _MonitoringThreadLoopOnce():
      try:
        async with connect(urlunparse(ws_url)) as ws:
          await asyncio.wait_for(self._LoopWS(ws=ws),
                                 timeout=ws_connect_interval)
      except asyncio.TimeoutError:
        pass
      except asyncio.CancelledError:
        raise
      except Exception:
        traceback.print_exc(file=sys.stderr)

    while not self._stop_event.is_set():
      try:
        await _MonitoringThreadLoopOnce()
      except asyncio.TimeoutError:
        pass
      except asyncio.CancelledError:
        raise
      except Exception:
        traceback.print_exc(file=sys.stderr)

  async def _CheckError(self):
    if self._monitoring_task.done():
      self._monitoring_task.result()
    if self._poll_task.done():
      self._poll_task.result()


class _DummyLock:

  def acquire(self):
    pass

  def release(self):
    pass

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    pass


class _JobContext:
  """Useful for catching errors when doing internal operations on a job, and the setting the status appropriately.
  """

  def __init__(self, *, job_id: str, comfy: ComfyCatapult):
    self._job_id = job_id
    self._comfy = comfy

  async def __aenter__(self):
    return self

  async def __aexit__(self, exc_type, exc_value, traceback):
    if exc_type is not None:
      async with self._comfy._lock:
        if self._job_id not in self._comfy._jobs:
          return
        job = self._comfy._jobs[self._job_id]
        if job.future is not None:
          job.future.set_exception(exc_value)
        if not job.status.IsDone():
          job.status = job.status._replace(errored=self._comfy._Now(),
                                           errors=job.status.errors +
                                           [exc_value])
        debug_path: Path | None = self._comfy._debug_path
        status = deepcopy(job.status)
      # Save the job status to a file
      if debug_path is not None:
        job_history_path = debug_path / f'{self._job_id}.status.yaml'
        await job_history_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(job_history_path, 'w') as f:
          await f.write(YamlDump(status))
        print(f'Wrote job status to {job_history_path}', file=sys.stderr)
