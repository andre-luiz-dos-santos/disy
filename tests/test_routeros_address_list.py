# coding=utf-8
import adapter
import unittest
from unittest import mock


@mock.patch('threading.Thread', mock.MagicMock())
class AddressListDict(unittest.TestCase):
    """
    Test address-list dict.
    """

    def test_listen_remove_while_getall_running(self):
        """
        /listen may report an item removal while /getall is running.
        The removed item must not be added to the list by the /getall handler.
        """
        fetch_1 = {'!re': '', '.tag': 'FETCH', '.id': '*1', 'address': '1.2.3.4', 'list': 'list_name_1_test'}
        fetch_2 = {'!re': '', '.tag': 'FETCH', '.id': '*2', 'address': '2.3.4.5', 'list': 'list_name_2_test'}
        remove_2 = {'!re': '', '.tag': 'LISTEN', '.id': '*2', '.dead': 'true'}
        fetch_done = {'!done': '', '.tag': 'FETCH'}

        routeros = mock.MagicMock()
        subject = adapter.AddressList(routeros)
        subject.write_fetch()

        subject.handle_sentence(fetch_1)
        self.assertListEqual(list(subject.values()), ['list_name_1_test'])

        subject.handle_sentence(remove_2)
        self.assertListEqual(list(subject.removed_ids), ['*2'])

        subject.handle_sentence(fetch_2)
        self.assertListEqual(list(subject.values()), ['list_name_1_test'])

        subject.handle_sentence(fetch_done)
        self.assertIsNone(subject.removed_ids)
        self.assertListEqual(list(subject.values()), ['list_name_1_test'])

    def test_listen_remove_while_getall_running_2(self):
        """
        Similar to the above, but the removal report is received after
        the /getall command has already added the item to self.
        """
        fetch_1 = {'!re': '', '.tag': 'FETCH', '.id': '*1', 'address': '1.2.3.4', 'list': 'list_name_1_test'}
        fetch_2 = {'!re': '', '.tag': 'FETCH', '.id': '*2', 'address': '2.3.4.5', 'list': 'list_name_2_test'}
        remove_2 = {'!re': '', '.tag': 'LISTEN', '.id': '*2', '.dead': 'true'}
        fetch_done = {'!done': '', '.tag': 'FETCH'}

        routeros = mock.MagicMock()
        subject = adapter.AddressList(routeros)
        subject.write_fetch()

        subject.handle_sentence(fetch_1)
        self.assertListEqual(list(subject.values()), ['list_name_1_test'])

        subject.handle_sentence(fetch_2)
        self.assertListEqual(list(subject.values()), ['list_name_1_test', 'list_name_2_test'])

        subject.handle_sentence(remove_2)
        self.assertListEqual(list(subject.removed_ids), [])

        subject.handle_sentence(fetch_done)
        self.assertIsNone(subject.removed_ids)
        self.assertListEqual(list(subject.values()), ['list_name_1_test'])

    def test_listen_add_while_getall_running(self):
        """
        The /listen sentences will always have the latest data.
        Only use /getall data when it hasn't been provided by /listen yet.
        """
        listen_1 = {'!re': '', '.tag': 'LISTEN', '.id': '*1', 'address': '1.2.3.4', 'list': 'list_name_1_test'}
        fetch_1 = {'!re': '', '.tag': 'FETCH', '.id': '*2', 'address': '1.2.3.4', 'list': 'list_name_old_test'}
        fetch_done = {'!done': '', '.tag': 'FETCH'}

        routeros = mock.MagicMock()
        subject = adapter.AddressList(routeros)
        subject.write_fetch()

        subject.handle_sentence(listen_1)
        self.assertListEqual(list(subject.values()), ['list_name_1_test'])

        subject.handle_sentence(fetch_1)
        self.assertListEqual(list(subject.values()), ['list_name_1_test'])

        subject.handle_sentence(fetch_done)
        self.assertIsNone(subject.removed_ids)
        self.assertListEqual(list(subject.values()), ['list_name_1_test'])
