# coding=utf-8
from copy import copy
import logging
import threading
import tikapy

log = logging.getLogger(__name__)


class Error(Exception):
    pass


class NotConnectedError(Error):
    pass


class Client:
    """
    Manage one connection to RouterOS.
    """

    def __init__(self, address, username, password):
        self.address = address
        self.username = username
        self.password = password
        self.connection = None
        self.lock = threading.Lock()

    def __call__(self, **kwargs):
        with self.lock:
            if self.connection is None:
                self._connect()
        return self

    def __enter__(self):
        if self.connection is None:
            raise NotConnectedError()
        self.lock.acquire()
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                self._disconnect()
        finally:
            self.lock.release()

    def _connect(self):
        self.connection = tikapy.TikapyClient(*self.address)
        self.connection.login(self.username, self.password)

    def _disconnect(self):
        try:
            self.connection.disconnect()
        except Exception:
            pass
        finally:
            self.connection = None

    def disconnect(self):
        with self.lock:
            self._disconnect()
