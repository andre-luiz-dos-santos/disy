# coding=utf-8
import adapter
import unittest
from unittest import mock


@mock.patch('threading.Thread', mock.MagicMock())
class AddressListDict(unittest.TestCase):
    """
    Test address-list dict.
    """

    def setUp(self):
        self.routeros = mock.NonCallableMagicMock()
        self.client = self.routeros.__enter__()
        m = mock.Mock()
        self.client.talk.return_value = m
        m.values.return_value = [
            {'.id': '*B01', 'list': 'listname_test', 'address': '8.7.6.5'},
            {'.id': '*B02', 'list': 'unknown_link', 'address': '0.1.2.3'},
        ]

    def test_fetch(self):
        subject = adapter.AddressList(self.routeros)
        subject.fetch()
        self.client.talk.assert_called_once_with(['/ip/firewall/address-list/getall', '=.proplist=.id,address,list'])
        self.assertEqual(subject['8.7.6.5'], 'listname_test')
        self.assertDictEqual(dict(subject), {
            '8.7.6.5': {'.id': '*B01', 'address': '8.7.6.5', 'list': 'listname_test'},
        })
        self.assertDictEqual(subject.by_id, {
            '*B01': {'.id': '*B01', 'address': '8.7.6.5', 'list': 'listname_test'},
        })
