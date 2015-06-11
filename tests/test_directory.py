# coding=utf-8
import os
import shutil
import unittest
import adapter
import adapter.directory


class DirectoryDict(unittest.TestCase):
    """
    Test directory dict.
    """

    TMP = '/tmp/path'

    def setUp(self):
        os.mkdir(self.TMP)
        os.mkdir(self.TMP + '/0.1.1.1')
        with open(self.TMP + '/regular_file', 'w') as f:
            f.write('Completely ignored')
        os.symlink('listname_test', self.TMP + '/6.2.3.4')
        os.symlink('unknown_link', self.TMP + '/0.9.8.7')

    def tearDown(self):
        shutil.rmtree(self.TMP)

    def test_fetch(self):
        d = adapter.Directory(self.TMP)
        self.assertDictEqual(dict(d), {'6.2.3.4': 'listname_test'})

    def test_fetch_pattern(self):
        subject = adapter.Directory(self.TMP, pattern=r'.*_link')
        self.assertDictEqual(dict(subject), {'0.9.8.7': 'unknown_link'})

    def test_add(self):
        subject = adapter.Directory(self.TMP)
        subject['2.2.2.2'] = 'new_test'
        self.assertDictEqual(dict(subject), {'2.2.2.2': 'new_test', '6.2.3.4': 'listname_test'})
        self.assertEqual(os.readlink(self.TMP + '/2.2.2.2'), 'new_test')
        subject.fetch()
        self.assertDictEqual(dict(subject), {'2.2.2.2': 'new_test', '6.2.3.4': 'listname_test'})

    def test_set(self):
        subject = adapter.Directory(self.TMP)
        subject['6.2.3.4'] = 'new_test'
        self.assertDictEqual(dict(subject), {'6.2.3.4': 'new_test'})
        self.assertEqual(os.readlink(self.TMP + '/6.2.3.4'), 'new_test')
        subject.fetch()
        self.assertDictEqual(dict(subject), {'6.2.3.4': 'new_test'})

    def test_remove(self):
        subject = adapter.Directory(self.TMP)
        del subject['6.2.3.4']
        self.assertDictEqual(dict(subject), {})
        self.assertFalse(os.path.lexists(self.TMP + '/6.2.3.4'))
        subject.fetch()
        self.assertDictEqual(dict(subject), {})

    def test_remove_missing(self):
        """
        A generic KeyError is raised when trying to delete a key that does not exist.
        """
        subject = adapter.Directory(self.TMP)
        with self.assertRaises(KeyError) as ctx:
            del subject['0.0.0.0']
        self.assertFalse(os.path.lexists(self.TMP + '/0.0.0.0'))
        self.assertNotIsInstance(ctx.exception, adapter.directory.Error)
        self.assertDictEqual(dict(subject), {'6.2.3.4': 'listname_test'})

    def test_remove_missing_file(self):
        """
        If only the symbolic link is missing, but the key is in the dict, do NOT raise anything.
        """
        subject = adapter.Directory(self.TMP)
        dict.__setitem__(subject, '0.0.0.0', 'xxx')
        self.assertFalse(os.path.lexists(self.TMP + '/0.0.0.0'))
        del subject['0.0.0.0']
        self.assertFalse(os.path.lexists(self.TMP + '/0.0.0.0'))
        self.assertDictEqual(dict(subject), {'6.2.3.4': 'listname_test'})

    def test_remove_directory(self):
        """
        Raise a directory.Error when the file that represents a key is not a symbolic link.
        """
        subject = adapter.Directory(self.TMP)
        dict.__setitem__(subject, '0.1.1.1', 'xxx')
        with self.assertRaises(adapter.directory.FileNotSymlinkError) as ctx:
            del subject['0.1.1.1']
        self.assertFalse(os.path.lexists(self.TMP + '/0.0.0.0'))
        self.assertIsInstance(ctx.exception, adapter.directory.Error)
        self.assertDictEqual(dict(subject), {'0.1.1.1': 'xxx', '6.2.3.4': 'listname_test'})
