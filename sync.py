# coding=utf-8
import logging
import threading
import time

log = logging.getLogger(__name__)


class Synchronizer:
    """
    Synchronize 'source' with 'dest'.
    """

    def __init__(self, source, dest):
        self.source = source
        self.dest = dest
        self.updated_condition = threading.Condition()

    def run(self):
        """
        Start 'watch' threads and
        wait for modifications on 'source' or 'dest'.
        """
        self.watch()
        self.wait()

    def wait(self):
        """
        Wait for the watch threads to report an update,
        and then call 'synchronize'.
        """
        with self.updated_condition:
            while True:
                try:
                    self.updated_condition.wait()
                    self.synchronize()
                    time.sleep(1)
                except Exception:
                    log.exception("Error synchronizing")
                    time.sleep(5)

    def synchronize(self):
        """
        Synchronize 'source' with 'dest'.
        """
        with self.source, self.dest:
            # Add / Update.
            for key, value in self.source.items():
                if key not in self.dest or self.dest[key] != value:
                    self.dest[key] = value
            # Remove.
            # Use 'tuple' to copy the keys, so that 'dest' may be modified within the for loop.
            for key in tuple(self.dest.keys()):
                if key not in self.source:
                    del self.dest[key]
            # Wait for all updates to complete.
            self.dest.flush()

    def watch(self):
        """
        Create a watch thread for 'source' and 'dest'.
        """
        for obj in [self.dest, self.source]:
            threading.Thread(target=self.watch_object,
                             args=(obj,),
                             daemon=True).start()

    def watch_object(self, obj):
        """
        Call and wait for function 'obj.watch' to return,
        and then notify 'updated_condition'.
        """
        while True:
            try:
                obj.watch()
            except Exception:
                log.exception("Error watching %s", obj)
                time.sleep(5)
            with self.updated_condition:
                self.updated_condition.notify()
