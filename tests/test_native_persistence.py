"""Portable release contracts: run on the target OS, never mock persistence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from feiyu import session
from feiyu.taskstate import TaskStore, TaskState, PersistenceError, atomic_json, workspace_id
from feiyu.verification import _read_safe

TEXT = '中文 简繁體 😀 𠮷'


class NativePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='feiyu-native-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'workspace'
        self.root.mkdir()
        override = patch.object(session, 'DIR', str(Path(self.temporary.name) / 'sessions'))
        override.start()
        self.addCleanup(override.stop)

    def test_durable_atomic_replace_and_safe_read(self):
        target = Path(self.temporary.name) / 'snapshot.json'
        for value in (TEXT, TEXT * 10000):
            atomic_json(target, {'text': value})
            raw, _ = _read_safe(target, 1024 * 1024)
            self.assertEqual(json.loads(raw), {'text': value})

    def test_workspace_identity_is_stable_and_distinct(self):
        other = Path(self.temporary.name) / 'other'
        other.mkdir()
        identity = workspace_id(self.root)
        self.assertEqual(identity, workspace_id(self.root))
        self.assertNotEqual(identity, workspace_id(other))

    def test_writer_restore_unknown_never_replays(self):
        store = TaskStore(self.root, 'native')
        self.addCleanup(store.close)
        with self.assertRaises(PersistenceError):
            TaskStore(self.root, 'native')
        state = TaskState('native', 'task', workspace_id(self.root))
        state.revise(TEXT)
        record = dict(id='operation', call_id='call', name='write_file', source='native-test',
                      cwd=str(self.root), started=1.0, args={})
        store.prepare(state, record)
        store.close()
        restored = TaskStore(self.root, 'native')
        self.addCleanup(restored.close)
        loaded = restored.recover()
        self.assertEqual(loaded.requests[0]['text'], TEXT)
        self.assertEqual(loaded.operations[0]['state'], 'unknown')
        with self.assertRaises(PersistenceError):
            restored.prepare(loaded, dict(record, id='replay'))
        self.assertEqual(len(loaded.operations), 1)
