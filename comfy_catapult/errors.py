# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# The Comfy Catapult project requires contributions made to this file be licensed
# under the MIT license or a compatible open source license. See LICENSE.md for
# the license text.

from copy import deepcopy
from typing import Sequence

from .comfy_schema import APINodeID, APIWorkflowTicket


class NodeNotFound(RuntimeError):

  def __init__(self, *, node_id: APINodeID | int | None,
               title: str | int | None):
    super().__init__(
        f'Node with title=={repr(title)}, node_id=={repr(node_id)} not found')
    self.node_id = node_id
    self.title = title


class MultipleNodesFound(RuntimeError):

  def __init__(self, *, search_titles: Sequence[str],
               search_nodes: Sequence[APINodeID], found_titles: Sequence[str],
               found_nodes: Sequence[APINodeID]):
    super().__init__(
        f'Found multiple nodes with titles=={repr(found_titles)}, node_ids=={list(found_nodes)}'
        f' when searching for titles=={repr(search_titles)}, node_ids=={list(search_nodes)}'
    )
    self.search_titles = list(search_titles)
    self.search_node_ids = list(search_nodes)
    self.found_titles = list(found_titles)
    self.found_node_ids = list(found_nodes)


class NodesNotExecuted(RuntimeError):

  def __init__(self, *, nodes: Sequence[APINodeID],
               titles: Sequence[str | None] | None):
    if titles is None:
      titles = [None] * len(nodes)
    if len(nodes) != len(titles):
      raise ValueError(
          f'len(nodes) != len(titles): {len(nodes)} != {len(titles)}')

    super().__init__(
        f'Nodes {",".join(map(repr, nodes))} with titles {",".join(map(repr,titles))} not executed'
    )
    self.nodes = list(nodes)
    self.titles = list(titles)


class WorkflowSubmissionError(RuntimeError):

  def __init__(self, msg, *, prepared_workflow: dict,
               ticket: APIWorkflowTicket):
    super().__init__(msg)
    self.prepared_workflow: dict = deepcopy(prepared_workflow)
    self.ticket: APIWorkflowTicket = deepcopy(ticket)


class URLValidationError(ValueError):
  pass


class BasedURLValidationError(ValueError):
  pass


class URLDirectoryValidationError(ValueError):
  pass
