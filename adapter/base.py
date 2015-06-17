# coding=utf-8
import threading

__all__ = (
    'Base',
    'ThreadedBase',
    'Error',
)


class Error(Exception):
    pass


class Base:
    """
    Adapters should behave like dict.
    After a set of updates, flush() must be called.
    One key cannot be updated twice, without a call to flush() in between.
    """

    def flush(self):
        pass

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class ThreadedBase(Base):
    """
    Simply adds a Lock() to Base.
    The lock must be held while the adapter is in use.
    """

    def __init__(self):
        self.lock = threading.Lock()
        super().__init__()

    def __enter__(self):
        self.lock.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.release()
