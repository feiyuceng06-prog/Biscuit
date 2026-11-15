import os
import sys
import unittest
from unittest.mock import Mock, patch
from feiyu.runtime import configure_frozen_environment


class TestFrozenEnvironment(unittest.TestCase):
    def configure(self, env, **kwargs):
        with patch.dict(os.environ, env, clear=True), \
             patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, '_MEIPASS', '/app/resources/backend/_internal', create=True), \
             patch.object(sys, 'platform', 'linux'):
            configure_frozen_environment()
            return dict(os.environ)

    def test_restore_user_libraries_and_remove_appimage_paths(self):
        env = {'APPDIR': '/app', 'LD_LIBRARY_PATH': '/app/resources/backend/_internal:/app/usr/lib:/user/lib',
               'LD_LIBRARY_PATH_ORIG': '/app/usr/lib:/user/lib', 'SSL_CERT_FILE': '/custom.pem'}
        result = self.configure(env)
        self.assertEqual(result['LD_LIBRARY_PATH'], '/user/lib')
        self.assertEqual(result['LD_LIBRARY_PATH_ORIG'], '/user/lib')
        self.assertEqual(result['SSL_CERT_FILE'], '/custom.pem')

    def test_no_bundle_path_leaks_without_original(self):
        result = self.configure({'LD_LIBRARY_PATH': '/app/resources/backend/_internal', 'SSL_CERT_DIR': '/custom'})
        self.assertNotIn('LD_LIBRARY_PATH', result)
        self.assertNotIn('LD_LIBRARY_PATH_ORIG', result)

    def test_source_process_is_unchanged(self):
        with patch.dict(os.environ, {'LD_LIBRARY_PATH': '/user/lib'}, clear=True), \
             patch.object(sys, 'frozen', False, create=True):
            configure_frozen_environment()
            self.assertEqual(dict(os.environ), {'LD_LIBRARY_PATH': '/user/lib'})

    def test_explicit_trust_store_is_not_overridden(self):
        with patch('feiyu.runtime.ssl.create_default_context') as create:
            result = self.configure({'SSL_CERT_FILE': '/missing.pem'})
        create.assert_not_called()
        self.assertEqual(result['SSL_CERT_FILE'], '/missing.pem')

    def test_empty_build_machine_store_uses_host_ca(self):
        empty = Mock(); empty.cert_store_stats.return_value = {'x509_ca': 0}
        loaded = Mock(); loaded.cert_store_stats.return_value = {'x509_ca': 10}
        with patch('feiyu.runtime.ssl.create_default_context', side_effect=[empty, loaded]), \
             patch('feiyu.runtime.os.path.isfile', return_value=True):
            result = self.configure({})
        self.assertEqual(result['SSL_CERT_FILE'], '/etc/ssl/certs/ca-certificates.crt')

    def test_working_default_store_is_preserved(self):
        loaded = Mock(); loaded.cert_store_stats.return_value = {'x509_ca': 10}
        with patch('feiyu.runtime.ssl.create_default_context', return_value=loaded):
            result = self.configure({})
        self.assertNotIn('SSL_CERT_FILE', result)
