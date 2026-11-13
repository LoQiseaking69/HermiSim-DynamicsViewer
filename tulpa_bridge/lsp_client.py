"""Minimal Language Server Protocol client for ``tulpa lsp`` (stdio, JSON-RPC 2.0).

Qt-free: responses and notifications are delivered to callbacks on a reader thread; the IDE
re-emits them as Qt signals.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def uri(path: str) -> str:
    return Path(path).resolve().as_uri()


def path_of(u: str) -> str:
    from urllib.parse import unquote, urlparse
    p = unquote(urlparse(u).path)
    if os.name == "nt" and p.startswith("/") and len(p) > 2 and p[2] == ":":
        p = p[1:]
    return p


class LspClient:
    def __init__(self, cmd: list[str], env: Optional[dict] = None,
                 on_diagnostics: Optional[Callable[[str, list], None]] = None) -> None:
        self.cmd, self.env = cmd, env
        self.on_diagnostics = on_diagnostics
        self._proc: Optional[subprocess.Popen] = None
        self._id = 0
        self._pending: dict[int, Callable[[Any], None]] = {}
        self._lock = threading.Lock()
        self._versions: dict[str, int] = {}
        self.ready = False

    # ------------------------------------------------------------------ lifecycle
    def start(self, root: str) -> None:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self._proc = subprocess.Popen(self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, env=self.env, creationflags=flags)
        threading.Thread(target=self._reader, daemon=True, name="lsp-reader").start()

        def _ready(_):
            self.ready = True
            self.notify("initialized", {})
        self.request("initialize", {"processId": os.getpid(), "rootUri": uri(root),
                                    "capabilities": {"textDocument": {"hover": {"contentFormat": ["markdown", "plaintext"]}}}},
                     _ready)

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self.request("shutdown", None, lambda _: self.notify("exit", None))
                self._proc.wait(1.0)
            except Exception:
                pass
            if self._proc.poll() is None:
                self._proc.kill()

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ------------------------------------------------------------------ wire
    def _write(self, msg: dict) -> None:
        if not self.alive:
            return
        body = json.dumps(msg).encode("utf-8")
        try:
            with self._lock:
                self._proc.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
                self._proc.stdin.flush()
        except (BrokenPipeError, OSError):
            logger.warning("tulpa lsp pipe closed")

    def request(self, method: str, params: Any, cb: Optional[Callable[[Any], None]] = None) -> int:
        with self._lock:
            self._id += 1
            rid = self._id
            if cb:
                self._pending[rid] = cb
        self._write({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        return rid

    def notify(self, method: str, params: Any) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _reader(self) -> None:
        out = self._proc.stdout
        while True:
            headers = {}
            while True:
                line = out.readline()
                if not line:
                    return
                line = line.decode("ascii", "replace").strip()
                if not line:
                    break
                k, _, v = line.partition(":")
                headers[k.lower()] = v.strip()
            n = int(headers.get("content-length", 0))
            data = out.read(n)
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            if "id" in msg and ("result" in msg or "error" in msg):
                cb = self._pending.pop(msg["id"], None)
                if cb:
                    try:
                        cb(msg.get("result"))
                    except Exception:
                        logger.debug("lsp callback failed", exc_info=True)
            elif msg.get("method") == "textDocument/publishDiagnostics" and self.on_diagnostics:
                p = msg.get("params", {})
                self.on_diagnostics(path_of(p.get("uri", "")), p.get("diagnostics", []))

    # ------------------------------------------------------------------ documents
    def open(self, path: str, text: str) -> None:
        self._versions[path] = 1
        self.notify("textDocument/didOpen", {"textDocument": {"uri": uri(path), "languageId": "tulpa",
                                                             "version": 1, "text": text}})

    def change(self, path: str, text: str) -> None:
        v = self._versions.get(path, 1) + 1
        self._versions[path] = v
        self.notify("textDocument/didChange", {"textDocument": {"uri": uri(path), "version": v},
                                               "contentChanges": [{"text": text}]})

    def close(self, path: str) -> None:
        self._versions.pop(path, None)
        self.notify("textDocument/didClose", {"textDocument": {"uri": uri(path)}})

    def _pos(self, path: str, line: int, col: int) -> dict:
        return {"textDocument": {"uri": uri(path)}, "position": {"line": line, "character": col}}

    def completion(self, path: str, line: int, col: int, cb) -> None:
        self.request("textDocument/completion", self._pos(path, line, col), cb)

    def hover(self, path: str, line: int, col: int, cb) -> None:
        self.request("textDocument/hover", self._pos(path, line, col), cb)

    def definition(self, path: str, line: int, col: int, cb) -> None:
        self.request("textDocument/definition", self._pos(path, line, col), cb)

    def symbols(self, path: str, cb) -> None:
        self.request("textDocument/documentSymbol", {"textDocument": {"uri": uri(path)}}, cb)
