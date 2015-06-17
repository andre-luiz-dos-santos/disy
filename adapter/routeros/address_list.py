# coding=utf-8
from collections import OrderedDict
import re
import logging
import threading
import time
from adapter.base import ThreadedBase, Error

__all__ = (
    'AddressList',
    'Error',
)

log = logging.getLogger(__name__)


def sentence_to_dict(sentence: list) -> dict:
    attrs = {}
    for word in sentence:
        try:
            second_eq_pos = word.index('=', 1)
        except ValueError:
            attrs[word.lstrip('=')] = ''
        else:
            attrs[word[:second_eq_pos].lstrip('=')] = word[second_eq_pos + 1:]
    return attrs


class AddressList(ThreadedBase, OrderedDict):
    """
    Maintains a local copy of /ip firewall address-list.
    """

    def __init__(self, routeros=None, pattern: str=None, **kwargs):
        self.by_id = {}
        self.removed_ids = None  # used during /getall
        self.next_tag = 0
        self.routeros = routeros
        self.pattern = re.compile(pattern or r'.+_test$')
        self.timeout = ['=timeout=%s' % kwargs['timeout']] if 'timeout' in kwargs else []
        self.update_event = threading.Event()
        super().__init__()
        self.commands = {}
        self.commands_update = threading.Condition()
        threading.Thread(target=self._reader, daemon=True).start()

    def __repr__(self):
        return 'AddressList(%r)' % (self.pattern.pattern,)

    def __str__(self):
        return 'address-list map (re=%r)' % (self.pattern.pattern,)

    def watch(self) -> True:
        log.debug("Waiting for updates.")
        self.update_event.wait()
        self.update_event.clear()
        log.debug("Reporting update.")
        return True

    def flush(self):
        log.debug("Waiting for %d commands to complete.", len(self.commands))
        with self.commands_update:
            while len(self.commands) > 0:
                self.commands_update.wait()
        log.debug("All done.")

    def get_tag(self):
        tag = '%X' % self.next_tag
        self.next_tag += 1
        return tag

    def write_fetch(self) -> None:
        log.debug("Writing getall command.")
        with self.routeros as client:
            cmd = ['/ip/firewall/address-list/getall',
                   '=.proplist=.id,address,list',
                   '.tag=FETCH']
            client._api.write_sentence(cmd)

    def enter_fetch_mode(self):
        if self.in_fetch_mode():
            log.debug("Already in fetch mode.")
        else:
            log.debug("Acquiring adapter lock.")
            self.lock.acquire()
        self.clear()
        self.by_id.clear()
        self.removed_ids = set()
        # No commands should be run in fetch mode.
        # If any threads were waiting on flush(), notify them.
        with self.commands_update:
            self.commands.clear()
            self.commands_update.notify_all()

    def in_fetch_mode(self):
        return self.removed_ids is not None

    def exit_fetch_mode(self):
        self.removed_ids = None
        self.lock.release()
        log.debug("Adapter lock released.")
        self.update_event.set()

    def write_listen(self) -> None:
        log.debug("Writing listen command.")
        with self.routeros as client:
            cmd = ['/ip/firewall/address-list/listen',
                   '=.proplist=.id,.dead,address,list',
                   '.tag=LISTEN']
            client._api.write_sentence(cmd)

    def write_add(self, address: str, list_name: str) -> str:
        log.debug("Writing add command: address=%r list_name=%r", address, list_name)
        tag = self.get_tag()
        with self.routeros as client:
            cmd = ['/ip/firewall/address-list/add',
                   '.tag=%s' % tag,
                   '=address=%s' % address,
                   '=list=%s' % list_name]
            cmd += self.timeout
            client._api.write_sentence(cmd)
        return tag

    def write_set(self, _id_: str, list_name: str) -> str:
        log.debug("Writing set command: id=%r list_name=%r", _id_, list_name)
        tag = self.get_tag()
        with self.routeros as client:
            cmd = ['/ip/firewall/address-list/set',
                   '.tag=%s' % tag,
                   '=.id=%s' % _id_,
                   '=list=%s' % list_name]
            cmd += self.timeout
            client._api.write_sentence(cmd)
        return tag

    def write_remove(self, _id_: str) -> str:
        log.debug("Writing remove command: _id_=%r", _id_)
        tag = self.get_tag()
        with self.routeros as client:
            cmd = ['/ip/firewall/address-list/remove',
                   '.tag=%s' % tag,
                   '=.id=%s' % _id_]
            client._api.write_sentence(cmd)
        return tag

    def read_sentence(self):
        d = self.routeros.connection._api.read_sentence()
        self.handle_sentence(sentence_to_dict(d))

    def handle_sentence(self, d: dict):
        if '!fatal' in d:
            log.error("Error from RouterOS: %r", d)
        elif '.tag' in d:
            if d['.tag'] == 'FETCH':
                self.handle_fetch_sentence(d)
            elif d['.tag'] == 'LISTEN':
                self.handle_listen_sentence(d)
            elif '!done' in d:
                try:
                    with self.commands_update:
                        c = self.commands.pop(d['.tag'])
                        if len(self.commands) == 0:
                            self.commands_update.notify_all()
                except KeyError:
                    log.debug("Unknown tag %r", d['.tag'])
                else:
                    c[0](c[1], d)
            else:
                log.debug("Unknown sentence: %r", d)
        else:
            log.debug("Sentence missing .tag: %r", d)

    def handle_fetch_sentence(self, d):
        """
        While fetching:
        d = {'!re': '', '.id': '*72', '.tag': 'FETCH', 'address': '1.2.3.4', 'list': 'list_name_test'}

        When done:
        d = {'!done': '', '.tag': 'FETCH'}
        """
        if '!done' in d:
            log.debug("Done fetching.")
            self.exit_fetch_mode()
        elif '!re' in d:
            if d['address'] in self:
                return  # /listen already provided this item
            if d['.id'] in self.removed_ids:
                return  # /listen reported this ID as removed
            if not self.pattern.match(d['list']):
                return
            super().__setitem__(d['address'], d)
            self.by_id[d['.id']] = d
        else:
            log.debug("Invalid FETCH-tagged sentence: %r", d)

    def handle_listen_sentence(self, d):
        """
        On addition or modification:
        {'!re': '', '.id': '*25E', '.tag': 'LISTEN', 'address': '5.6.7.1', 'list': 'list_name_test'}

        On removal:
        {'!re': '', '.dead': 'true', '.id': '*25A', '.tag': 'LISTEN'}
        """
        if '.dead' in d:
            self.handle_remote_removal(d)
        elif 'address' in d and 'list' in d:
            self.handle_remote_addition(d)
        else:
            log.debug("Invalid LISTEN-tagged sentence: %r", d)

    def handle_remote_addition(self, sentence):
        """
        {'!re': '', '.id': '*25E', '.tag': 'LISTEN', 'address': '1.2.3.4', 'list': 'list_name_test'}
        """
        try:
            d = super().__getitem__(sentence['address'])
        except KeyError:
            _id_ = sentence['.id']
            d = {'.id': _id_,
                 'address': sentence['address'],
                 'list': sentence['list']}
            super().__setitem__(d['address'], d)
            self.by_id[_id_] = d
            log.debug("Item remotely added: %r", d)
            self.update_event.set()
        else:
            if d['list'] != sentence['list']:
                d['list'] = sentence['list']
                log.debug("Item remotely changed: %r", d)
                self.update_event.set()

    def handle_remote_removal(self, d):
        """
        {'!re': '', '.dead': 'true', '.id': '*25E', '.tag': 'LISTEN'}
        """
        try:
            d = self.by_id[d['.id']]
        except KeyError:
            self.removed_ids.add(d['.id'])
        else:
            log.debug("Item remotely removed: %r", dict(self.by_id[d['.id']]))
            super().__delitem__(d['address'])
            del self.by_id[d['.id']]
            self.update_event.set()

    def handle_add_response(self, c: tuple, sentence: dict):
        """
        c = ('5.6.7.8', 'list_name_test')
        sentence = {'!done': '', '.tag': '5E', 'ret': '*25E'}
        """
        _id_ = sentence['ret']
        d = {'.id': _id_,
             'address': c[0],
             'list': c[1]}
        super().__setitem__(d['address'], d)
        self.by_id[_id_] = d
        log.debug("Item added: %r", d)

    def handle_set_response(self, c: tuple, sentence: dict):
        """
        c = ('*25F', 'list_name_test')
        sentence = {'!done': '', '.tag': '0'}
        """
        _id_, list_name = c
        d = self.by_id[_id_]
        d['list'] = list_name
        log.debug("Item changed: %r", d)

    def handle_remove_response(self, c: tuple, sentence: dict):
        """
        c = ('*25F', '1.2.3.4')
        sentence = {'!done': '', '.tag': '0'}
        """
        _id_, address = c
        log.debug("Item removed: %r", dict(self.by_id[_id_]))
        super().__delitem__(address)
        del self.by_id[_id_]

    def __getitem__(self, address: str):
        return super().__getitem__(address)['list']

    def __setitem__(self, address: str, list_name: str):
        log.debug('%r %r' % (address, list_name))
        try:
            d = super().__getitem__(address)
        except KeyError:
            tag = self.write_add(address, list_name)
            self.commands[tag] = (self.handle_add_response, (address, list_name))
        else:
            tag = self.write_set(d['.id'], list_name)
            self.commands[tag] = (self.handle_set_response, (d['.id'], list_name))

    def __delitem__(self, address: str):
        log.debug('%r' % (address,))
        try:
            d = super().__getitem__(address)
        except KeyError:
            pass
        else:
            tag = self.write_remove(d['.id'])
            self.commands[tag] = (self.handle_remove_response, (d['.id'], address))

    def _reader(self) -> None:
        while True:
            try:
                with self.routeros(connect=True):
                    self.enter_fetch_mode()
                self.write_listen()
                self.write_fetch()
                while True:
                    self.read_sentence()
            except Exception:
                log.exception("Error in RouterOS reading thread.")
                self.routeros.disconnect()
                time.sleep(1)
