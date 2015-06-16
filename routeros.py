# coding=utf-8
from copy import copy
import logging
import threading
import tikapy

log = logging.getLogger(__name__)


class Client:
    """
    Manage one connection to RouterOS.
    """

    def __init__(self, address, username, password):
        self.address = address
        self.username = username
        self.password = password
        self.connection = None
        self.semaphore = threading.Semaphore()
        self.close_on_exit = False

    def __enter__(self):
        """
        Connect to RouterOS server or use the last connection established.
        """
        if self.connection is None:
            self.connect()
        self.semaphore.acquire(blocking=True)
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        On RouterOS error, disconnect from server.
        """
        try:
            if self.close_on_exit is True \
                    or (exc_type is not None
                        and issubclass(exc_type, tikapy.ClientError)):
                self.disconnect()
        finally:
            self.semaphore.release()

    def copy(self):
        """
        Copy self, minus the established connection and its semaphore.
        """
        new = copy(self)
        new.connection = None
        new.semaphore = threading.Semaphore()
        new.close_on_exit = True
        return new

    def connect(self):
        """
        Connect to RouterOS server.
        """
        self.connection = tikapy.TikapyClient(*self.address)
        self.connection.login(self.username, self.password)

    def disconnect(self):
        try:
            self.connection.disconnect()
        except Exception:
            pass
        finally:
            self.connection = None
