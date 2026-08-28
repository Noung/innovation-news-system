#!/usr/bin/env python3
"""Credential-free TCP gateway from host loopback to the isolated Admin API."""

from __future__ import annotations

import selectors
import socket
import socketserver


UPSTREAM = ("admin", 3001)


class GatewayHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        with socket.create_connection(UPSTREAM, timeout=5) as upstream:
            self.request.setblocking(False)
            upstream.setblocking(False)
            selector = selectors.DefaultSelector()
            selector.register(self.request, selectors.EVENT_READ, upstream)
            selector.register(upstream, selectors.EVENT_READ, self.request)
            try:
                while True:
                    events = selector.select(timeout=30)
                    if not events:
                        return
                    for key, _mask in events:
                        data = key.fileobj.recv(65536)
                        if not data:
                            return
                        key.data.sendall(data)
            finally:
                selector.close()


class ThreadingGateway(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with ThreadingGateway(("0.0.0.0", 8080), GatewayHandler) as server:
        print("local-gateway: forwarding 0.0.0.0:8080 to admin:3001", flush=True)
        server.serve_forever()
