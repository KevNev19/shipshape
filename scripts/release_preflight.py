#!/usr/bin/env python3
"""Run the canonical standalone release-preflight template from the kit."""

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

TEMPLATE = (
    Path(__file__).resolve().parent.parent / "templates" / "scripts" / "release-preflight.py.tmpl"
)


class _RenderedTemplateLoader(importlib.machinery.SourceFileLoader):
    """Load the substituted template as the program the wrapper used to run."""

    def __init__(self, fullname: str, path: str, source: str) -> None:
        super().__init__(fullname, path)
        self._source = source

    def get_data(self, path: str) -> bytes:
        return self._source.encode("utf-8")


def main() -> None:
    try:
        source = TEMPLATE.read_text(encoding="utf-8").replace("{{KIT_VERSION}}", "development")
        module_name = "shipshape_release_preflight"
        loader = _RenderedTemplateLoader(module_name, str(TEMPLATE), source)
        spec = importlib.util.spec_from_loader(module_name, loader)
        if spec is None:
            raise ImportError("The bundled release preflight could not be loaded.")
        module = importlib.util.module_from_spec(spec)
        module.__file__ = str(TEMPLATE)
        previous = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            loader.exec_module(module)
            raise SystemExit(module.main())
        finally:
            sys.dont_write_bytecode = previous
    except SystemExit:
        raise
    except Exception:
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": [
                        {
                            "code": "entrypoint_error",
                            "message": "The bundled release preflight could not be loaded.",
                        }
                    ],
                    "next_action": "Repair the shipshape installation before releasing.",
                },
                indent=2,
                sort_keys=True,
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
