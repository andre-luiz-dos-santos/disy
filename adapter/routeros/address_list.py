# coding=utf-8
import re
import logging
import threading
import time

__all__ = (
    'AddressList',
    'Error',
)

log = logging.getLogger(__name__)


class Error(Exception):
    pass


class AddressList(dict):
    """
    Maintains a local copy of /ip firewall address-list.
    """

    def __init__(self, routeros=None, pattern: str=None, **kwargs):
        self.by_id = {}
        self.routeros = routeros
        self.pattern = re.compile(pattern or r'.+_test$')
        self.timeout = ['=timeout=%s' % kwargs['timeout']] if 'timeout' in kwargs else []
        self.update_event = threading.Event()
        super().__init__()
        threading.Thread(target=self._listen, daemon=True).start()

    def __repr__(self):
        return 'AddressList(%r)' % (self.pattern.pattern,)

    def __str__(self):
        return 'address-list map (re=%r)' % (self.pattern.pattern,)

    def watch(self) -> True:
        """
        Wait until the address list changes.
        """
        self.update_event.wait()
        self.update_event.clear()
        self.fetch()
        return True

    def fetch(self) -> None:
        """
        Fetch the entire address list from the RouterOS server.
        """
        with self.routeros as client:
            self.clear()
            self.by_id.clear()
            for d in client.talk(['/ip/firewall/address-list/getall',
                                  '=.proplist=.id,address,list']).values():
                if self.pattern.match(d['list']):
                    super().__setitem__(d['address'], d)
                    self.by_id[d['.id']] = d

    def __getitem__(self, address: str):
        return super().__getitem__(address)['list']

    def __setitem__(self, address: str, list_name: str):
        try:
            d = super().__getitem__(address)
        except KeyError:
            # 'address' is not on self yet.
            # Add it.
            with self.routeros as client:
                i = client.talk(['/ip/firewall/address-list/add',
                                 '=address=%s' % address,
                                 '=list=%s' % list_name]
                                + self.timeout)
                d = {'.id': i,
                     'address': address,
                     'list': list_name}
                super().__setitem__(address, d)
                self.by_id[i] = d
                log.debug('Added %r', d)
        else:
            # 'address' is already on self.
            # Set it if it belongs to a different list.
            if d['list'] != list_name:
                with self.routeros as client:
                    client.talk(['/ip/firewall/address-list/set',
                                 '=.id=%s' % d['.id'],
                                 '=list=%s' % list_name]
                                + self.timeout)
                    d['list'] = list_name
                    log.debug('Updated %r', d)

    def __delitem__(self, address: str):
        d = super().__getitem__(address)
        with self.routeros as client:
            client.talk(['/ip/firewall/address-list/remove',
                         '=.id=%s' % d['.id']])
            super().__delitem__(address)
            del self.by_id[d['.id']]
            log.debug('Removed %r', d)

    def _listen(self) -> None:
        """
        Listen for updates.
        """
        while True:
            try:
                with self.routeros.copy() as client:
                    self.update_event.set()
                    for d in client.listen(['/ip/firewall/address-list/listen',
                                            '=.proplist=.id,.dead,address,list']):
                        log.debug('Received %r', d)
                        try:
                            # Record has been deleted.
                            if '.dead' in d:
                                if d['.id'] not in self.by_id:
                                    log.debug('ID %r not found',
                                              d['.id'])
                                    continue
                            # Record has been added or modified.
                            else:
                                if not self.pattern.match(d['list']):
                                    log.debug('List %r does not match pattern %r',
                                              d['list'], self.pattern.pattern)
                                    continue
                                if self[d['address']] == d['list']:
                                    log.debug("Address %r already in list %r",
                                              d['address'], d['list'])
                                    continue
                        except KeyError:
                            pass
                        self.update_event.set()
            except Exception:
                time.sleep(1)
                log.exception('Error while listening for address-list changes')
            finally:
                self.update_event.set()
