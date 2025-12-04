import socket
import struct

import json

from .utils import *

import logging

_logger = logging.getLogger(__name__)


class SocketConnection:
    connection = dict()

    @staticmethod
    def log_connection(func):
        def wrapper(self, id, *args, **kwargs):
            client = self.check_connection(id)
            if not client:
                raise ConnectionError(f"No active connection for id: {id}")
            _logger.info(f"Connection status for {id}: {client if client else 'inactive'}")
            return func(self, id, client, *args, **kwargs)

        return wrapper

    def check_connection(self, id) -> socket.socket | bool:
        client = self.connection.get(id)
        if not client:
            return False
        try:
            client.send(b"", socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL)
            return client
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    def connect(self, host: str | tuple, id: int, timeout=10) -> socket.socket | None:
        if client := self.connection.get(id):
            if self.check_connection(client):
                _logger.info("Using existing connection")
                return client

        _logger.info(f"Creating new connection to {host}")

        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(timeout)
            client.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 20)
            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
            client.connect(host)
            _logger.info(f"Connected to {host}")
        except Exception as e:
            _logger.error(f"Connection failed: {e}")
            return None
        else:
            self.connection[id] = client
            return client

    @log_connection
    def send(self, id: int, client: socket.socket | None, data: dict, code: int, connection, **kwargs) -> bytes | None:
        header = bytearray(default_header_bytes)
        added_bytes_to_header(header, generate_dynamic_headers_data(code))
        if code == 2:
            sending_data = generate_hdm_key(connection.hdm_password, json.dumps(data))
        else:
            sending_data = generate_second_key(connection.hdm_key, json.dumps(data))

        added_bytes_to_header(header, [len(sending_data).to_bytes(2, 'big'), sending_data])

        client.sendall(header)

        try:
            response = client.recv(2048)
            _logger.info(f'Recv information: {response}')
            connection.hdm_seq += 1
            return response
        except socket.timeout:
            _logger.error("Timed out")
        except ConnectionRefusedError:
            _logger.error("Connection refused.")
        except Exception as e:
            _logger.error(e)

    @log_connection
    def close(self, id, client: socket.socket | None = None, connection=None):
        if client:
            try:
                try:
                    client.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                _logger.info("Socket close")
            except Exception as e:
                _logger.warning(f"Error while closing socket: {e}")
            finally:
                try:
                    client.close()
                except Exception as e:
                    _logger.error(f"Error closing socket + connection: {e}")
                finally:
                    self.connection.pop(id)
                    connection.hdm_key = ''


HDM = SocketConnection()
