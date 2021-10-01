from typing import Callable, Awaitable, Union
import typing
import os


class Connection:
    """Abstract class to serve a session and send/receive messages to the
    client."""

    async def send(self, message: str) -> None:
        raise NotImplementedError

    async def receive(self) -> str:
        raise NotImplementedError


class ConnectionManager:
    """Base class for handling incoming connections."""

    def __init__(self, on_connect_cb: Callable[[Connection], Awaitable[None]]) -> None:
        raise NotImplementedError

    def run(self) -> None:
        raise NotImplementedError


class ConnectionClosed(Exception):
    """Raised when a Connection is closed from the other side."""

    pass


# =============================================================================
# FastAPIConnection / FastAPIConnectionManager
# =============================================================================

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from htmltools import tag_list, html_document, html_dependency
from .html_dependencies import shiny_deps


class FastAPIConnection(Connection):
    def __init__(self, websocket: WebSocket) -> None:
        self._websocket: WebSocket = websocket

    async def send(self, message: str) -> None:
        await self._websocket.send_text(message)

    async def receive(self) -> str:
        try:
            return await self._websocket.receive_text()
        except WebSocketDisconnect:
            raise ConnectionClosed


class FastAPIConnectionManager(ConnectionManager):
    """Implementation of ConnectionManager which listens on a HTTP port to serve a web
    page, and also listens for WebSocket connections."""

    def __init__(
        self,
        ui,
        on_connect_cb: Callable[[Connection], Awaitable[None]],
        on_session_request_cb: Callable[[Request], Awaitable[Response]],
    ) -> None:
        self._ui = ui
        self._on_connect_cb: Callable[[Connection], Awaitable[None]] = on_connect_cb
        self._on_session_request_cb: Callable[
            [Request], Awaitable[Response]
        ] = on_session_request_cb
        self._fastapi_app: FastAPI = FastAPI()

        # TODO: make routes more configurable?
        @self._fastapi_app.get("/")
        async def get(request: Request) -> Response:
            ui = self._ui(request) if callable(self._ui) else self._ui
            if isinstance(ui, Response):
                return ui
            if isinstance(ui, tag_list):
                ui.append(shiny_deps())

                def register_dep(d):
                    return create_web_dependency(self._fastapi_app, d)

                res = ui.render(process_dep=register_dep)
                return HTMLResponse(content=res["html"])
            return HTMLResponse(status_code=500, content="Invalid UI object")

        # TODO: does this actually prevent noticable overhead compared to processing dependencies individually?
        # (by processing dependencies individually, we might have a shot at sensible static rendering behavior)
        # self._fastapi_app.mount(
        #    "/shared",
        #    StaticFiles(directory = os.path.join(os.path.dirname(__file__), "www/shared")),
        #    name = "shared"
        # )

        @self._fastapi_app.api_route(
            "/session/{rest_of_path:path}", methods=["GET", "POST"]
        )
        async def route_session_request(request: Request) -> Response:
            return await self._on_session_request_cb(request)

        @self._fastapi_app.websocket("/websocket/")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()

            conn = FastAPIConnection(websocket)
            await self._on_connect_cb(conn)

        if typing.TYPE_CHECKING:
            # The only purpose of this block is to make the type checker not
            # warn about these functions not being accessed.
            [get, route_session_request, websocket_endpoint]

    def run(self) -> None:
        uvicorn.run(self._fastapi_app, host="0.0.0.0", port=8000)


def create_web_dependency(api: FastAPI, dep: html_dependency, scrub_file: bool = True):
    if dep.src.get("href", None) is None:
        prefix = dep.name + "-" + str(dep.version)
        f = dep.src["file"]
        path = os.path.join(package_dir(dep.package), f) if dep.package else f
        api.mount("/" + prefix, StaticFiles(directory=path), name=prefix)
        dep.src["href"] = prefix
    if scrub_file and "file" in dep.src:
        del dep.src["file"]
    return dep


# similar to base::system.file()
# TODO: find proper home for this
import tempfile
import importlib


def package_dir(package: str) -> str:
    with tempfile.TemporaryDirectory():
        pkg_file = importlib.import_module(".", package=package).__file__
        return os.path.dirname(pkg_file)


# =============================================================================
# TCPConnection / TCPConnectionManager
# =============================================================================

import asyncio
from asyncio import StreamReader, StreamWriter


class TCPConnection(Connection):
    def __init__(self, reader: StreamReader, writer: StreamWriter) -> None:
        self._reader: StreamReader = reader
        self._writer: StreamWriter = writer

    async def send(self, message: str) -> None:
        self._writer.write(message.encode("utf-8"))

    async def receive(self) -> str:
        data: bytes = await self._reader.readline()
        if not data:
            raise ConnectionClosed

        message: str = data.decode("latin1").rstrip()
        return message


class TCPConnectionManager(ConnectionManager):
    """Implementation of ConnectionManager which listens on a TCP port."""

    def __init__(self, on_connect_cb: Callable[[Connection], Awaitable[None]]) -> None:
        self._on_connect_cb: Callable[[Connection], Awaitable[None]] = on_connect_cb

    def run(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        server = await asyncio.start_server(
            self._handle_incoming_connection, "127.0.0.1", 8888
        )

        addr = server.sockets[0].getsockname()
        print(f"Serving on {addr}")

        # Run event loop to listen for events
        async with server:
            await server.serve_forever()

    async def _handle_incoming_connection(
        self, reader: StreamReader, writer: StreamWriter
    ) -> None:
        # When incoming connection arrives, spawn a session
        conn = TCPConnection(reader, writer)
        await self._on_connect_cb(conn)
