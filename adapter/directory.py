# coding=utf-8
import contextlib
import os
import re
import logging
import stat
import time
from adapter.base import Base, Error

__all__ = (
    'Directory',
    'Error',
    'FileNotSymlinkError',
)

log = logging.getLogger(__name__)


class FileNotSymlinkError(Error):
    pass


class Directory(Base, dict):
    """
    Access to directory.
    """

    def __init__(self, path: str, pattern: str=None):
        self.path = path
        self.mtime = os.path.getmtime(self.path)
        self.pattern = re.compile(pattern or r'.+_test$')
        super().__init__()
        self.fetch()

    def __repr__(self):
        return 'Directory(%r, %r)' % (self.path, self.pattern.pattern)

    def __str__(self):
        return 'directory map (path=%r, re=%r)' % (self.path, self.pattern.pattern)

    def changed(self):
        cur = os.path.getmtime(self.path)
        if cur != self.mtime:
            self.mtime = cur
            return True
        return False

    def watch(self):
        while True:
            time.sleep(1)
            if self.changed():
                self.fetch()
                return True

    def fetch(self):
        self.clear()
        for key in os.listdir(self.path):
            file = os.path.join(self.path, key)
            try:
                value = os.readlink(file)
            except (FileNotFoundError, OSError):
                pass  # file was deleted or was not a symlink.
            else:
                if self.pattern.match(value):
                    super().__setitem__(key, value)

    def __setitem__(self, key: str, value: str):
        file = os.path.join(self.path, key)
        while True:
            try:
                os.symlink(value, file)
            except FileExistsError:
                with contextlib.suppress(KeyError):
                    del self[key]
            else:
                super().__setitem__(key, value)
                return

    def __delitem__(self, key: str):
        file = os.path.join(self.path, key)
        try:
            x = os.lstat(file)
            if stat.S_ISLNK(x.st_mode):
                os.unlink(file)
                with contextlib.suppress(KeyError):
                    super().__delitem__(key)
            else:
                raise FileNotSymlinkError(file)
        except FileNotFoundError:
            super().__delitem__(key)
