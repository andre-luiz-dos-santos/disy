# coding=utf-8
import unittest
from unittest import mock
import collections
import sync


def wrap_dict(obj):
    mock_obj = mock.MagicMock(wraps=obj)
    mock_obj.__getitem__.side_effect = obj.__getitem__
    mock_obj.__setitem__.side_effect = obj.__setitem__
    mock_obj.__delitem__.side_effect = obj.__delitem__
    mock_obj.flush = mock.Mock()
    return mock_obj


class DictSynchronization(unittest.TestCase):
    """
    Test synchronization.
    """

    def test_add_1(self):
        s, d = {'1.2.3.4': 'a_test'}, wrap_dict({})
        sync.Synchronizer(s, d).synchronize()
        d.__setitem__.assert_called_once_with('1.2.3.4', 'a_test')

    def test_remove_1(self):
        s, d = {}, wrap_dict({'1.2.3.4': 'a_test'})
        sync.Synchronizer(s, d).synchronize()
        d.__delitem__.assert_called_once_with('1.2.3.4')

    def test_set_1(self):
        s, d = {'1.2.3.4': 'a_test'}, wrap_dict({'1.2.3.4': 'b_test'})
        sync.Synchronizer(s, d).synchronize()
        d.__setitem__.assert_called_once_with('1.2.3.4', 'a_test')

    def test_add_and_remove_1(self):
        remote = collections.OrderedDict([('5.4.3.2', 'b_test'), ('9.9.9.9', 'old')])
        local = collections.OrderedDict([('1.2.3.4', 'a_test'), ('9.9.9.9', 'new')])
        remote_mock = wrap_dict(remote)
        sync.Synchronizer(local, remote_mock).synchronize()
        remote_mock.assert_has_calls([
            ('__setitem__', ('1.2.3.4', 'a_test')),
            mock.ANY,
            ('__setitem__', ('9.9.9.9', 'new')),
            mock.ANY,
            ('__delitem__', ('5.4.3.2',)),
        ])
        result = collections.OrderedDict([('9.9.9.9', 'new'), ('1.2.3.4', 'a_test')])
        self.assertDictEqual(result, remote)
