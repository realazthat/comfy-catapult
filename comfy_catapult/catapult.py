# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import asyncio
import datetime
import enum
import json
import logging
import textwrap
import threading
import traceback as tb
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pprint import pformat
from typing import Any, Dict, Generic, List, Optional, Sequence, Tuple, TypeVar
from urllib.parse import ParseResult, urlparse

import aiofiles
from anyio import Path
from slugify import slugify
from websockets import WebSocketClientProtocol, connect

from .api_client import ComfyAPIClientBase
from .catapult_base import (ComfyCatapultBase, ExceptionInfo, JobStatus,
                            Progress)
from .comfy_schema import (APIHistory, APIHistoryEntry,
                           APIHistoryEntryStatusNote, APINodeID, APIQueueInfo,
                           APISystemStats, APIWorkflowTicket, WSMessage)
from .comfy_utils import TryParseAsModel, YamlDump
from .errors import JobFailed, NodesNotExecuted, WorkflowSubmissionError

logger = logging.getLogger(__name__)


@dataclass
class _Job:

  class RemoteStatus(enum.Enum):
    NONE = enum.auto()
    PENDING_OR_RUNNING = enum.auto()

  job_id: str
  prepared_workflow: dict
  important_nodes: Tuple[APINodeID, ...]
  ticket: Optional[APIWorkflowTicket]
  status: JobStatus
  # Exceptions that should be in status but aren't because they're not pickable
  # or deepcopyable.
  errors: List[Exception]
  future: 'asyncio.Future[dict]'
  remote_job_status: RemoteStatus
  job_debug_path: Optional[Path]


T = TypeVar('T')


@dataclass
class _Guess(Generic[T]):
  value: Optional[T]
  updated: datetime.datetime


class ComfyCatapult(ComfyCatapultBase):

  def __init__(self,
               comfy_client: ComfyAPIClientBase,
               *,
               debug_path: Optional[Path],
               debug_save_all: bool = False):
    """_summary_

    Args:
        comfy_client (ComfyAPIClientBase): _description_
        debug_path (Path | None): For logging of certain debug information, in
          case of errors.
        debug_save_all (bool, optional): If set, as much information as possible
          will be saved to the debug_path. Defaults to False.
    """
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
    self._debug_save_all = debug_save_all

  async def __aenter__(self):
    await self._comfy_client.__aenter__()
    return self

  async def __aexit__(self, exc_type, exc_value, traceback):
    await self.Close()

  async def Close(self):

    self._stop_event.set()

    async with self._lock:
      for job in self._jobs.values():
        job.future.cancel()
    await self._CheckError()
    async with self._lock:
      monitoring_task = self._monitoring_task
      poll_task = self._poll_task
    monitoring_task.cancel()
    poll_task.cancel()
    try:
      await monitoring_task
    except asyncio.CancelledError:
      pass
    try:
      await poll_task
    except asyncio.CancelledError:
      pass

  async def Catapult(
      self,
      *,
      job_id: str,
      prepared_workflow: dict,
      important: Sequence[APINodeID],
      job_debug_path: Optional[Path] = None,
  ) -> dict:
    async with self._lock:
      if job_id in self._jobs:
        raise KeyError(f'User job id {json.dumps(job_id)} already exists')
      if not slugify(job_id) == job_id:
        raise ValueError(
            f'User job id {json.dumps(job_id)} is not slugified (e.g {json.dumps(slugify(job_id))})'
        )
      if job_debug_path is None and self._debug_path is not None:
        dt = datetime.datetime.now(datetime.timezone.utc).isoformat()
        job_debug_path = self._debug_path / f'{slugify(dt)}-{slugify(job_id)}'

    if job_debug_path is not None:
      await job_debug_path.mkdir(parents=True, exist_ok=True)

    future: asyncio.Future[dict] = asyncio.Future()
    async with self._lock:
      self._jobs[job_id] = _Job(
          job_id=job_id,
          prepared_workflow=prepared_workflow,
          important_nodes=tuple(important),
          ticket=None,
          future=future,
          status=JobStatus(scheduled=self._Now(),
                           running=None,
                           pending=None,
                           success=None,
                           errored=None,
                           cancelled=None,
                           errors=[]),
          errors=[],
          remote_job_status=_Job.RemoteStatus.PENDING_OR_RUNNING,
          job_debug_path=job_debug_path)

    async with _JobContext(job_id=job_id, comfy=self):
      ticket: APIWorkflowTicket = await self._comfy_client.PostPrompt(
          prompt_workflow=prepared_workflow)

      async with self._lock:
        self._jobs[job_id].ticket = ticket
        if ticket.prompt_id is not None:
          self._prompt_id_index[ticket.prompt_id] = job_id

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

      if ticket.prompt_id is None:
        raise AssertionError(
            'ticket.prompt_id is None, should be impossible here')
      return await future

  async def GetStatus(self, *,
                      job_id: str) -> 'Tuple[JobStatus, asyncio.Future[dict]]':
    async with self._lock:
      if job_id not in self._jobs:
        raise KeyError(f'Job id {json.dumps(job_id)} not found')
      job = self._jobs[job_id]
      return deepcopy(job.status), job.future

  async def GetExceptions(self, *, job_id: str) -> List[Exception]:
    async with self._lock:
      if job_id not in self._jobs:
        raise KeyError(f'Job id {json.dumps(job_id)} not found')
      job = self._jobs[job_id]
      return list(job.errors)

  async def CancelJob(self, *, job_id: str):
    async with _JobContext(job_id=job_id, comfy=self):
      async with self._lock:
        ticket: Optional[APIWorkflowTicket] = self._jobs[job_id].ticket
        prompt_id: Optional[str] = None
        if ticket is not None:
          prompt_id = ticket.prompt_id
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

  async def _ReceivedJobHistory(self, *, job_id: str, history: APIHistory,
                                job_context: '_JobContext'):
    if not isinstance(history, APIHistory):
      raise AssertionError(f'history must be APIHistory, not {type(history)}')

    async with self._lock:
      prepared_workflow: dict = deepcopy(self._jobs[job_id].prepared_workflow)
      ticket: Optional[APIWorkflowTicket] = deepcopy(self._jobs[job_id].ticket)
      prompt_id: Optional[str] = None
      if ticket is not None:
        prompt_id = ticket.prompt_id
      important_nodes = deepcopy(self._jobs[job_id].important_nodes)

    if len(history.root) == 0:
      return
    if prompt_id not in history.root:
      raise AssertionError(
          f'prompt_id {json.dumps(prompt_id)} not in history.root')
    if not isinstance(prompt_id, str):
      raise AssertionError(f'prompt_id must be str, not {type(prompt_id)}')
    job_history: APIHistoryEntry = history.root[prompt_id]
    async with self._lock:
      self._jobs[job_id].status = self._jobs[job_id].status._replace(
          job_history=job_history.model_dump())

    ##########################################################################
    # Get outputs_to_execute, outputs_with_data, extra_data
    extra_data: Optional[dict] = None
    outputs_to_execute: List[APINodeID] = []
    outputs_with_data: List[APINodeID] = []
    if job_history.outputs is not None:
      outputs_with_data = list(job_history.outputs.keys())
    if job_history.prompt is not None:
      if job_history.prompt.extra_data is not None:
        extra_data = job_history.prompt.extra_data
      if job_history.prompt.outputs_to_execute is not None:
        outputs_to_execute = job_history.prompt.outputs_to_execute
    logger.debug('extra_data: %s', YamlDump(extra_data))

    if job_history.status is not None:
      if job_history.status.completed is False:
        notes: List[str] = []
        if job_history.status.messages is not None:
          note: APIHistoryEntryStatusNote
          for note in job_history.status.messages:
            notes.append(textwrap.indent(pformat(note._asdict()), prefix='  '))
        # TODO: Turn all Exception into a subclass of Exception.
        # TODO: Make all exceptions going forward contain the metadata that
        # NodesNotExecuted does.
        raise JobFailed('Job has failed'
                        f'\n  status: {repr(job_history.status)}'
                        f'\n  notes:' + '\n'.join(notes))

    ##########################################################################
    logger.debug('job_history.prompt.extra_data.model_dump(): %s',
                 YamlDump(extra_data))
    logger.debug('job_history.prompt.outputs_to_execute.model_dump(): %s',
                 YamlDump(outputs_to_execute))

    logger.debug('outputs_to_execute: %s', YamlDump(outputs_to_execute))
    logger.debug('outputs_that_executed: %s', YamlDump(outputs_with_data))

    bad_dataless_outputs = [
        node_id for node_id in outputs_to_execute
        if node_id not in outputs_with_data
    ]

    def _GetTitles(node_ids: List[APINodeID]) -> List[Optional[str]]:
      titles = []
      for node_id in node_ids:
        node_info: dict = prepared_workflow.get(node_id, {})
        meta: dict = node_info.get('_meta', {})
        title: Optional[str] = meta.get('title', None)
        titles.append(title)
      return titles

    if len(bad_dataless_outputs) > 0:
      logger.error('bad_dataless_outputs: %s', YamlDump(bad_dataless_outputs))
      logger.error('_GetTitles(bad_dataless_outputs): %s',
                   YamlDump(_GetTitles(bad_dataless_outputs)))

    dataless_important_outputs = [
        node_id for node_id in bad_dataless_outputs
        if node_id in important_nodes
    ]
    if len(dataless_important_outputs) > 0:
      logger.error('dataless_important_outputs: %s',
                   YamlDump(dataless_important_outputs))
      logger.error('_GetTitles(dataless_important_outputs): %s',
                   YamlDump(_GetTitles(dataless_important_outputs)))
      raise NodesNotExecuted(nodes=list(dataless_important_outputs),
                             titles=_GetTitles(dataless_important_outputs))

    # await self._eta_estimator.RecordFinished(job_id=job_id)

    now = self._Now()
    async with self._lock:
      job = self._jobs[job_id]
      job.future.set_result(job_history.model_dump())
      job.status = job.status._replace(success=now)

  async def _GetJobIDs(self) -> List[str]:
    async with self._lock:
      return list(self._jobs.keys())

  async def _Poll(self):
    ############################################################################
    await self._CheckError()
    await self._PollFutures()
    ############################################################################
    await self._PollSystemStats()
    ############################################################################
    prompt_id_2_status: Dict[str, str] = {}
    await self._PollQueue(prompt_id_2_status)

    ############################################################################
    prompt_info: dict = await self._comfy_client.GetPromptRaw()

    exec_info = prompt_info['exec_info']
    queue_remaining = exec_info['queue_remaining']
    if not isinstance(queue_remaining, int):
      raise AssertionError(
          f'queue_remaining must be int, not {type(queue_remaining)}')
    logger.info('queue_remaining: %s', queue_remaining)
    ############################################################################
    # Check the /history endpoint to see if there are any updates on our jobs.
    await self._PollHistory(prompt_id_2_status=prompt_id_2_status)

  async def _PollFutures(self):
    ############################################################################
    # Make sure any hanging future that is done matches the job status.
    done_futures_jobs: List[str] = []
    async with self._lock:
      job_id: str
      job: _Job
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

  async def _PollSystemStats(self):
    system_stats: APISystemStats = await self._comfy_client.GetSystemStats()
    logger.info('system_stats: %s', YamlDump(system_stats.model_dump()))
    for job_id in await self._GetJobIDs():
      async with _JobContext(job_id=job_id, comfy=self):
        async with self._lock:
          job = self._jobs[job_id]
          if job.status.IsDone():
            continue
          if job.status.system_stats_check is None:
            job.status = job.status._replace(system_stats_check=self._Now())

  async def _PollQueue(self, prompt_id_2_status: Dict[str, str]):
    """Check /queue endpoint and update job status.
    """
    queue_info: APIQueueInfo = await self._comfy_client.GetQueue()

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

    logger.info('pending_count: %s', pending_count)
    logger.info('running_count: %s', running_count)

    for prompt_id, status in prompt_id_2_status.items():
      async with self._lock:
        if prompt_id not in self._prompt_id_index:
          continue
        job_id = self._prompt_id_index[prompt_id]
        async with _JobContext(job_id=job_id, comfy=self):
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
          job.status = job.status._replace(queue_check=self._Now())

    # TODO: Reenable this or remove it.
    # print('self._jobs:', file=sys.stderr)
    # pprint(self._jobs, indent=2, stream=sys.stderr)

  async def _PollHistory(self, prompt_id_2_status: Dict[str, str]):
    # Update job.remote_job_status.
    for job_id in await self._GetJobIDs():
      async with _JobContext(job_id=job_id, comfy=self) as job_context:
        async with self._lock:
          new_remote_job_status = (_Job.RemoteStatus.NONE
                                   if job_id not in prompt_id_2_status else
                                   _Job.RemoteStatus.PENDING_OR_RUNNING)
          self._jobs[job_id].remote_job_status = new_remote_job_status

    # Update job.job_history.
    for job_id in await self._GetJobIDs():
      async with _JobContext(job_id=job_id, comfy=self) as job_context:
        async with self._lock:
          if job_id in prompt_id_2_status:
            # In this case, it's pending or running, not going to be in the
            # `/history` endpoint.
            continue

          if self._jobs[job_id].status.job_history is not None:
            # We already have the job history.
            continue

          ticket: Optional[APIWorkflowTicket] = self._jobs[job_id].ticket
          prompt_id: Optional[str] = None
          if ticket is not None:
            prompt_id = ticket.prompt_id

          if prompt_id is None:
            # This should never happen, but :shrug:.
            continue
          job_debug_path = self._jobs[job_id].job_debug_path
          errors_dump_directory: Optional[Path] = None
          if job_debug_path is not None:
            errors_dump_directory = job_debug_path / 'errors'

        ########################################################################
        history_raw: dict = await self._comfy_client.GetHistoryRaw(
            prompt_id=prompt_id)
        await job_context.WatchVar(history_raw=history_raw)
        history: APIHistory = await TryParseAsModel(
            content=history_raw,
            model_type=APIHistory,
            errors_dump_directory=errors_dump_directory)
        await self._ReceivedJobHistory(job_id=job_id,
                                       history=history,
                                       job_context=job_context)
        ########################################################################

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
    prompt_id: Optional[str]
    node_id: Optional[str]
    node_type: Optional[str]

    while True:
      try:
        logger.debug('websocket recv')
        out = await ws.recv()
        if not isinstance(out, str):
          logger.debug('websocket type(out): %s', type(out))
          continue
        logger.debug('websocket raw: %s', YamlDump(out))
        errors_dump_directory: Optional[Path] = None
        async with self._lock:
          if self._debug_path is not None:
            errors_dump_directory = self._debug_path / 'errors'

        message = await TryParseAsModel(
            content=json.loads(out),
            model_type=WSMessage,
            errors_dump_directory=errors_dump_directory)
        logger.debug('websocket message: %s', YamlDump(message.__dict__))

        if message.type == 'executing' and 'last_node_id' in message.data:
          last_node_id = message.data['last_node_id']

          async with self._lock:
            self._guess_currently_running_node_id = _Guess(value=last_node_id,
                                                           updated=self._Now())
          await self._Record()
        elif message.type == 'executing' and 'node' in message.data and 'prompt_id' in message.data:
          prompt_id = message.data.get('prompt_id', None)
          node_id = message.data.get('node', None)
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
          prompt_id = message.data.get('prompt_id', None)
          node_id = message.data.get('node', None)
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
          prompt_id = message.data.get('prompt_id', None)
          node_id = message.data.get('node_id', None)
          node_type = message.data.get('node_type', None)
          # executed: Optional[list] = message.data.get('executed', None)
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
                        ExceptionInfo(
                            type=str(node_type),
                            message=
                            f'Node {json.dumps(node_id)} of type {json.dumps(str(node_type))} errored:\n{textwrap.indent(YamlDump(message.data), "  ")}',
                            traceback='',
                            attributes={})
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
        logger.exception('Error in _LoopWS')

  async def _PollLoop(self):
    while not self._stop_event.is_set():
      try:
        await asyncio.sleep(5)
        await self._Poll()
      except asyncio.CancelledError:
        raise
      except Exception:
        logger.exception('Error in _PollLoop')

  async def _MonitoringThread(self):

    async with self._lock:
      client_id = self._client_id
      comfy_api_url: str = self._comfy_client.GetURL()
      ws_connect_interval: float = self._ws_connect_interval

    # replace protocol with ws, using a url library
    ws_url: ParseResult = urlparse(comfy_api_url)
    if ws_url.scheme == 'https':
      ws_url = ws_url._replace(scheme='wss')
    else:
      ws_url = ws_url._replace(scheme='ws')
    ws_url = ws_url._replace(path='/ws')
    ws_url = ws_url._replace(query=f'clientId={client_id}')

    async def _MonitoringThreadLoopOnce():
      try:
        async with connect(ws_url.geturl()) as ws:
          await asyncio.wait_for(self._LoopWS(ws=ws),
                                 timeout=ws_connect_interval)
      except asyncio.TimeoutError:
        pass
      except asyncio.CancelledError:
        raise
      except Exception:
        logger.exception('Error in _MonitoringThreadLoopOnce')

    while not self._stop_event.is_set():
      try:
        await _MonitoringThreadLoopOnce()
      except asyncio.TimeoutError:
        pass
      except asyncio.CancelledError:
        raise
      except Exception:
        logger.exception('Error in _MonitoringThreadLoopOnce')

  async def _CheckError(self):
    async with self._lock:
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
    self._watch_vars: Dict[str, Any] = {}

  async def WatchVar(self, **kwargs):
    for name, value in kwargs.items():
      self._watch_vars[name] = value
    async with self._comfy._lock:
      job = self._comfy._jobs[self._job_id]
      job_debug_path: Optional[Path] = job.job_debug_path
    if job_debug_path is None:
      return
    if self._comfy._debug_save_all:
      dt = datetime.datetime.now(datetime.timezone.utc).isoformat()
      for name, value in kwargs.items():
        dump_path = job_debug_path / 'watch' / f'{slugify(dt)}-{slugify(name)}.yaml'
        await dump_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(dump_path, 'w') as f:
          await f.write(YamlDump(value))

  async def __aenter__(self):
    return self

  async def __aexit__(self, exc_type, exc_value, traceback):
    if exc_type is not None:
      async with self._comfy._lock:
        if self._job_id not in self._comfy._jobs:
          return
        job = self._comfy._jobs[self._job_id]
        if job.future is not None and not job.future.done():
          job.future.set_exception(exc_value)
        if not job.status.IsDone():
          job.errors += [exc_value]
          exc_info = ExceptionInfo(type=exc_type.__name__,
                                   message=str(exc_value),
                                   traceback=''.join(
                                       tb.format_exception(
                                           exc_type, exc_value, traceback)),
                                   attributes={
                                       k: str(v)
                                       for k, v in exc_value.__dict__.items()
                                   })
          job.status = job.status._replace(errored=self._comfy._Now(),
                                           errors=job.status.errors +
                                           [exc_info])
        job_debug_path: Optional[Path] = job.job_debug_path
        status = deepcopy(job.status)
        workflow = deepcopy(job.prepared_workflow)
        ticket = deepcopy(job.ticket)
        remote_job_status = deepcopy(job.remote_job_status)

      dt = datetime.datetime.now(datetime.timezone.utc).isoformat()
      if job_debug_path is not None:
        dump = {
            'job_id': self._job_id,
            'exc_type': exc_type,
            'exc_value': str(exc_value),
            'traceback': tb.format_exception(exc_type, exc_value, traceback),
            'job_status': status,
            'remote_job_status': remote_job_status,
            'ticket': ticket,
            'watch_vars': self._watch_vars,
            'workflow': workflow,
        }
        job_dump_path = job_debug_path / 'context-dumps' / f'{slugify(dt)}.dump.yaml'
        await job_dump_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(job_dump_path, 'w') as f:
          await f.write(YamlDump(dump))
        logger.error(f'Wrote job status to {json.dumps(str(job_dump_path))}.')
