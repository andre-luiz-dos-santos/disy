# coding=utf-8
import logging
import threading
import routeros_api

log = logging.getLogger(__name__)
routeros_api.RouterOsApiPool.socket_timeout = None


class Client:
    """
    Manage one connection to RouterOS.
    """

    def __init__(self, address, username, password):
        self.address = address
        self.username = username
        self.password = password
        self.connection = None
        self.mutex = threading.Lock()

    def __enter__(self):
        """
        Connect to RouterOS server or use the last connection established.
        """
        with self.mutex:
            if self.connection is None:
                self.connect()
            return self.api

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        On RouterOS error, disconnect from server.
        """
        with self.mutex:
            if exc_type is not None:
                if self.connection:
                    try:
                        self.connection.disconnect()
                    finally:
                        self.connection = None

    def connect(self):
        """
        Connect to RouterOS server.
        """
        self.connection = routeros_api.RouterOsApiPool(
            self.address[0],
            self.username,
            self.password,
            self.address[1])
        self.api = self.connection.get_api()
