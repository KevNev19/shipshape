#!/usr/bin/env python3
"""Load the canonical rendered review-gates implementation for kit tests."""

import importlib.machinery
import sys
from pathlib import Path

_TEMPLATE = (
    Path(__file__).resolve().parent.parent / "templates" / "scripts" / "review-gates.py.tmpl"
)
_SOURCE = _TEMPLATE.read_text(encoding="utf-8").replace("{{KIT_VERSION}}", "development")


class _RenderedTemplateLoader(importlib.machinery.SourceFileLoader):
    """Load the substituted template without a second copy of the implementation."""

    def __init__(self, fullname: str, path: str, source: str) -> None:
        super().__init__(fullname, path)
        self._source = source

    def get_data(self, path: str) -> bytes:
        return self._source.encode("utf-8")


def _load() -> None:
    """Run the template in this module under this module's name.

    Tracebacks keep the template path. Bytecode is not written beside it.
    """
    module = sys.modules[__name__]
    loader = _RenderedTemplateLoader(__name__, str(_TEMPLATE), _SOURCE)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous


_load()
