# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

import asyncio
import base64
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
from typing import (Any, Dict, Generic, List, Optional, Sequence, Tuple,
                    TypeVar, Union, overload)
from urllib.parse import unquote as paramdecode
from urllib.parse import urlparse

import aiofiles
from anyio import Path
from slugify import slugify
from typing_extensions import Literal
from websockets import WebSocketClientProtocol, connect

from .api_client import ComfyAPIClientBase
from .catapult_base import (ComfyCatapultBase, ExceptionInfo, JobID, JobStatus,
                            Progress)
from .comfy_schema import (APIHistory, APIHistoryEntry,
                           APIHistoryEntryStatusNote, APINodeID, APIQueueInfo,
                           APISystemStats, APIWorkflowTicket, PromptID,
                           WSMessage)
from .comfy_utils import TryParseAsModel, YamlDump
from .errors import (JobFailed, JobNotFound, NodesNotExecuted,
                     WorkflowSubmissionError)
from .url_utils import JoinToBaseURL

logger = logging.getLogger(__name__)

_JobQueueStatus = Literal['pending', 'running', 'not_in_queue']


def _BasicAuthToHeaders(*, url: str, headers: Dict[str, str]) -> str:
  """
  websockets lib doessn't support basic auth in the url, so we have to move it
  to the headers.
  """
  url_pr = urlparse(url)
  if url_pr.username is None and url_pr.password is None:
    return url

  username = url_pr.username or ''
  password = url_pr.password or ''

  # urldecode the username and password
  username = paramdecode(username)
  password = paramdecode(password)
  auth = f'{username}:{password}'
  encoded_auth = base64.b64encode(auth.encode()).decode()

  headers['Authorization'] = f'Basic {encoded_auth}'
  new_netloc = f'{url_pr.hostname}:{url_pr.port}'
  return url_pr._replace(netloc=new_netloc).geturl()


def _GetWebSocketURL(*, comfy_api_url: str, client_id: str) -> str:
  ws_url_str = JoinToBaseURL(comfy_api_url, 'ws')
  ws_url = urlparse(ws_url_str)
  if ws_url.scheme == 'https':
    ws_url = ws_url._replace(scheme='wss')
  else:
    ws_url = ws_url._replace(scheme='ws')
  ws_url = ws_url._replace(query=f'clientId={client_id}')
  return ws_url.geturl()


@dataclass
class _Job:

  class RemoteStatus(enum.Enum):
    NONE = enum.auto()
    PENDING_OR_RUNNING = enum.auto()

  job_id: JobID
  prepared_workflow: dict
  important_nodes: Tuple[APINodeID, ...]
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

    self._jobs: Dict[JobID, _Job] = {}
    # {ticket.prompt_id -> job_id}
    self._prompt_id_index: Dict[PromptID, JobID] = {}

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
    self._loop_delay: float = 2.
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

  @overload
  async def Catapult(
      self,
      *,
      job_id: JobID,
      prepared_workflow: dict,
      important: Sequence[APINodeID],
      use_future_api: Literal[True],
      job_debug_path: Optional[Path] = None
  ) -> Tuple[JobStatus, 'asyncio.Future[dict]']:
    ...

  @overload
  async def Catapult(self,
                     *,
                     job_id: JobID,
                     prepared_workflow: dict,
                     important: Sequence[APINodeID],
                     use_future_api: Literal[False] = False,
                     job_debug_path: Optional[Path] = None) -> dict:
    ...

  async def Catapult(
      self,
      *,
      job_id: JobID,
      prepared_workflow: dict,
      important: Sequence[APINodeID],
      use_future_api: bool = False,
      job_debug_path: Optional[Path] = None,
  ) -> Union[dict, Tuple[JobStatus, 'asyncio.Future[dict]']]:
    # TODO: Deprecate use_future_api==False at version>=3.0.
    status, future = await self._CatapultInternal(
        job_id=job_id,
        prepared_workflow=prepared_workflow,
        important=important,
        job_debug_path=job_debug_path)
    if use_future_api:
      return status, future
    return await future

  async def _CatapultInternal(
      self,
      *,
      job_id: JobID,
      prepared_workflow: dict,
      important: Sequence[APINodeID],
      job_debug_path: Optional[Path] = None,
  ) -> Tuple[JobStatus, 'asyncio.Future[dict]']:
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
    job = _Job(job_id=job_id,
               prepared_workflow=prepared_workflow,
               important_nodes=tuple(important),
               future=future,
               status=JobStatus(scheduled=self._Now(),
                                comfy_scheduled=None,
                                running=None,
                                pending=None,
                                success=None,
                                errored=None,
                                cancelled=None,
                                system_stats_check=None,
                                queue_check=None,
                                ticket=None,
                                job_history=None,
                                errors=[]),
               errors=[],
               remote_job_status=_Job.RemoteStatus.PENDING_OR_RUNNING,
               job_debug_path=job_debug_path)

    async with self._lock:
      self._jobs[job_id] = job

    async with _JobContext(job_id=job_id, catapult=self):
      ticket: APIWorkflowTicket = await self._comfy_client.PostPrompt(
          prompt_workflow=prepared_workflow)

      async with self._lock:
        job.status = job.status._replace(ticket=ticket)
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
      async with self._lock:
        job.status = job.status._replace(comfy_scheduled=self._Now())

      async with self._lock:
        return deepcopy(job.status), job.future

  async def GetStatus(
      self, *, job_id: JobID) -> 'Tuple[JobStatus, asyncio.Future[dict]]':
    async with self._lock:
      job = await self._GetJob(job_id=job_id)
      return deepcopy(job.status), job.future

  async def GetExceptions(self, *, job_id: JobID) -> List[Exception]:
    async with self._lock:
      job = await self._GetJob(job_id=job_id)
      return list(job.errors)

  async def _GetJob(self, *, job_id: JobID) -> _Job:
    """Get a job by job_id, raising JobNotFound if it doesn't exist.

    Must be called within a lock.
    """
    if job_id not in self._jobs:
      raise JobNotFound(f'Job id {json.dumps(job_id)} not found')
    return self._jobs[job_id]

  async def CancelJob(self, *, job_id: JobID):
    async with _JobContext(job_id=job_id, catapult=self):
      async with self._lock:
        job: _Job = await self._GetJob(job_id=job_id)
        ticket: Optional[APIWorkflowTicket] = job.status.ticket
        prompt_id: Optional[PromptID] = None
        if ticket is not None:
          prompt_id = ticket.prompt_id
        remote_job_status = job.remote_job_status

      if remote_job_status == _Job.RemoteStatus.PENDING_OR_RUNNING \
          and prompt_id is not None:
        # TODO(realazthat/comfy-catapult#5): We don't know for sure that the
        # current job is the one we're cancelling, as there could be a race
        # condition here.
        await self._comfy_client.PostInterrupt()
        await self._comfy_client.PostQueue(delete=[prompt_id], clear=False)

        async with self._lock:
          job.remote_job_status = _Job.RemoteStatus.NONE

      now = self._Now()
      async with self._lock:
        if not job.status.IsDone():
          job.status = job.status._replace(cancelled=now)
          job.future.cancel()

  async def _ReceivedJobHistory(self, *, job_id: JobID, history: APIHistory,
                                queue_status: _JobQueueStatus,
                                job_context: '_JobContext'):
    if not isinstance(history, APIHistory):
      raise AssertionError(f'history must be APIHistory, not {type(history)}')

    async with self._lock:
      job: _Job = await self._GetJob(job_id=job_id)

    async with self._lock:
      prepared_workflow: dict = deepcopy(job.prepared_workflow)
      ticket: Optional[APIWorkflowTicket] = deepcopy(job.status.ticket)
      prompt_id: Optional[PromptID] = None
      if ticket is not None:
        prompt_id = ticket.prompt_id
      important_nodes = deepcopy(job.important_nodes)

    if len(history.root) == 0:
      if queue_status == 'not_in_queue':
        raise Exception(
            'Job disappeared from the ComfyUI. Perhaps ComfyUI was'
            ' restarted, due to a very bad crash, e.g a GPU crash or'
            ' a segfault.'
            f'\n  job_id: {json.dumps(job_id)}'
            f'\n  prompt_id: {json.dumps(prompt_id)}')
      return
    if prompt_id not in history.root:
      raise AssertionError(
          f'prompt_id {json.dumps(prompt_id)} not in history.root')
    if not isinstance(prompt_id, str):
      raise AssertionError(f'prompt_id must be str, not {type(prompt_id)}')
    job_history: APIHistoryEntry = history.root[prompt_id]
    async with self._lock:
      job.status = job.status._replace(job_history=job_history.model_dump())

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
      job.future.set_result(job_history.model_dump())
      job.status = job.status._replace(success=now)

  async def _GetJobIDs(self) -> List[JobID]:
    async with self._lock:
      return list(self._jobs.keys())

  async def _Poll(self):
    ############################################################################
    job_ids = await self._GetJobIDs()
    ############################################################################
    await self._CheckError()
    await self._PollFutures()
    ############################################################################
    await self._PollSystemStats(job_ids=job_ids)
    ############################################################################
    job_id_2_status: Dict[JobID, _JobQueueStatus]
    job_id_2_status = await self._PollQueue(job_ids=job_ids)
    ############################################################################
    prompt_info: dict = await self._comfy_client.GetPromptRaw()

    exec_info = prompt_info['exec_info']
    queue_remaining: int = exec_info['queue_remaining']
    if not isinstance(queue_remaining, int):
      raise AssertionError(
          f'queue_remaining must be int, not {type(queue_remaining)}')
    logger.info('queue_remaining: %s', queue_remaining)
    ############################################################################
    # Check the /history endpoint to see if there are any updates on our jobs.
    await self._PollHistory(job_id_2_status=job_id_2_status)

  async def _PollFutures(self):
    ############################################################################
    # Make sure any hanging future that is done matches the job status.
    done_futures_jobs: List[JobID] = []
    async with self._lock:
      job_id: JobID
      job: _Job
      for job_id, job in self._jobs.items():
        if job.future.done() and not job.status.IsDone():
          done_futures_jobs.append(job_id)
    for job_id in done_futures_jobs:
      try:
        async with _JobContext(job_id=job_id, catapult=self):
          async with self._lock:
            job = await self._GetJob(job_id=job_id)
            # See if an error occurred.
            job.future.result()
            job.status = job.status._replace(success=self._Now())
      except Exception:
        logger.exception(
            f'Error in _PollFutures for job_id {json.dumps(job_id)}. Continuing.'
        )

  async def _PollSystemStats(self, *, job_ids: List[JobID]):
    system_stats: APISystemStats = await self._comfy_client.GetSystemStats()
    logger.info('system_stats: %s', YamlDump(system_stats.model_dump()))
    for job_id in job_ids:
      try:
        async with _JobContext(job_id=job_id, catapult=self):
          async with self._lock:
            job = await self._GetJob(job_id=job_id)
            if job.status.IsDone():
              continue
            if job.status.system_stats_check is None:
              job.status = job.status._replace(system_stats_check=self._Now())
      except Exception:
        logger.exception(
            f'Error in _PollFutures for job_id {json.dumps(job_id)}. Continuing.'
        )

  async def _PollQueue(self, *,
                       job_ids: List[JobID]) -> Dict[JobID, _JobQueueStatus]:
    """Check /queue endpoint and update job status.
    """

    queue_info: APIQueueInfo = await self._comfy_client.GetQueue()
    prompt_id_2_status: Dict[PromptID, _JobQueueStatus] = {}
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

    job_id_2_status: Dict[JobID, _JobQueueStatus] = {}
    for prompt_id, status in prompt_id_2_status.items():
      async with self._lock:
        if prompt_id not in self._prompt_id_index:
          continue
        job_id = self._prompt_id_index[prompt_id]
        if job_id not in job_ids:
          continue
        job_id_2_status[job_id] = status
    for job_id in job_ids:
      if job_id not in job_id_2_status:
        job_id_2_status[job_id] = 'not_in_queue'

    for job_id, status in job_id_2_status.items():
      try:
        async with _JobContext(job_id=job_id, catapult=self):
          async with self._lock:
            job: _Job = await self._GetJob(job_id=job_id)

            if status == 'pending' and job.status.pending is None:
              job.status = job.status._replace(pending=self._Now())

            if status == 'running' and job.status.running is None:
              job.status = job.status._replace(running=self._Now())
              self._guess_currently_running_job_id = _Guess(value=job_id,
                                                            updated=self._Now())
              self._guess_currently_running_node_id = _Guess(
                  value=None, updated=self._Now())
              self._guess_currently_running_node_progress = _Guess(
                  value=None, updated=self._Now())
            job.status = job.status._replace(queue_check=self._Now())
      except Exception:
        logger.exception(
            f'Error in _PollQueue for job_id {json.dumps(job_id)}. Continuing.')

    # TODO: Reenable this or remove it.
    # print('self._jobs:', file=sys.stderr)
    # pprint(self._jobs, indent=2, stream=sys.stderr)
    return job_id_2_status

  async def _PollHistoryUpdateRemoteJobStatus(
      self, job_id_2_status: Dict[JobID, _JobQueueStatus], job_id: JobID):
    async with _JobContext(job_id=job_id, catapult=self):
      async with self._lock:
        job = await self._GetJob(job_id=job_id)
        new_remote_job_status = (_Job.RemoteStatus.NONE
                                 if job_id not in job_id_2_status else
                                 _Job.RemoteStatus.PENDING_OR_RUNNING)
        job.remote_job_status = new_remote_job_status

  async def _PollHistoryUpdateJobHistory(self, *, job_id: JobID,
                                         queue_status: _JobQueueStatus):
    async with _JobContext(job_id=job_id, catapult=self) as job_context:
      async with self._lock:
        job: _Job = await self._GetJob(job_id=job_id)

        if job.status.job_history is not None:
          # We already have the job history.
          return

        ticket: Optional[APIWorkflowTicket] = job.status.ticket
        prompt_id: Optional[PromptID] = None
        if ticket is not None:
          prompt_id = ticket.prompt_id

        if prompt_id is None:
          # This should never happen, but :shrug:.
          raise Exception(
              'prompt_id is None; this should never happen, because'
              ' we should have a ticket as soon as we submit a job.')
        job_debug_path = job.job_debug_path
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
                                     queue_status=queue_status,
                                     job_context=job_context)
      ########################################################################

  async def _PollHistory(self, job_id_2_status: Dict[JobID, _JobQueueStatus]):
    # Update job.remote_job_status.
    for job_id in job_id_2_status.keys():
      try:
        await self._PollHistoryUpdateRemoteJobStatus(job_id_2_status,
                                                     job_id=job_id)
      except Exception:
        logger.exception(
            f'Error in _PollHistory for job_id {json.dumps(job_id)}. Continuing.'
        )

    # Update job.job_history.
    for job_id, queue_status in job_id_2_status.items():
      if queue_status in ['pending', 'running']:
        # In this case, it's pending or running, not going to be in the
        # `/history` endpoint.
        continue
      try:
        await self._PollHistoryUpdateJobHistory(job_id=job_id,
                                                queue_status=queue_status)
      except Exception:
        logger.exception(
            f'Error in _PollHistory for job_id {json.dumps(job_id)}. Continuing.'
        )

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
    prompt_id: Optional[PromptID]
    node_id: Optional[str]
    node_type: Optional[str]

    # Only sleep if there is an error to prevent overflow to the logs; otherwise
    # poll ws.recv() as fast as possible.
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
              job = await self._GetJob(job_id=job_id)
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
              job = await self._GetJob(job_id=job_id)
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
              job = await self._GetJob(job_id=job_id)
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
              job = await self._GetJob(job_id=job_id)
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
        await asyncio.sleep(self._loop_delay)

  async def _PollLoop(self):
    while not self._stop_event.is_set():
      try:
        await self._Poll()
      except asyncio.CancelledError:
        raise
      except Exception:
        logger.exception('Error in _PollLoop')
      await asyncio.sleep(self._loop_delay)

  async def _MonitoringThread(self):

    async with self._lock:
      client_id = self._client_id
      comfy_api_url: str = self._comfy_client.GetURL()
      ws_connect_interval: float = self._ws_connect_interval

    ws_url = urlparse(
        _GetWebSocketURL(comfy_api_url=comfy_api_url, client_id=client_id))

    ws_headers: Dict[str, str] = {}
    ws_url = urlparse(
        _BasicAuthToHeaders(url=ws_url.geturl(), headers=ws_headers))

    async def _MonitoringThreadLoopOnce():
      nonlocal ws_url
      try:
        # websockets lib doessn't support basic auth in the url, so we have to
        # move it to the headers.

        async with connect(ws_url.geturl(), extra_headers=ws_headers) as ws:
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
      await asyncio.sleep(self._loop_delay)

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

  def __init__(self, *, job_id: JobID, catapult: ComfyCatapult):
    self._job_id = job_id
    self._catapult = catapult
    self._watch_vars: Dict[str, Any] = {}

  async def WatchVar(self, **kwargs):
    for name, value in kwargs.items():
      self._watch_vars[name] = value
    async with self._catapult._lock:
      job = await self._catapult._GetJob(job_id=self._job_id)
      job_debug_path: Optional[Path] = job.job_debug_path
    if job_debug_path is None:
      return
    if self._catapult._debug_save_all:
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
      async with self._catapult._lock:
        if self._job_id not in self._catapult._jobs:
          return
        job = await self._catapult._GetJob(job_id=self._job_id)
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
          job.status = job.status._replace(errored=self._catapult._Now(),
                                           errors=job.status.errors +
                                           [exc_info])
        job_debug_path: Optional[Path] = job.job_debug_path
        status = deepcopy(job.status)
        workflow = deepcopy(job.prepared_workflow)
        ticket = deepcopy(job.status.ticket)
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
