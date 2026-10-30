"""Regression checks for shared terminal/keep-awake helpers."""
import unittest
from unittest.mock import patch
from continuous_mode import Awake
from native_goal_control import blank_input

class InputTests(unittest.TestCase):
    def test_empty_and_dim_placeholder_only(self):
        self.assertTrue(blank_input('› ',2))
        self.assertTrue(blank_input('\x1b[0;2m› Ask Codex to do anything\x1b[0m',2))
        self.assertFalse(blank_input('› user draft',12))
        self.assertFalse(blank_input('› user draft',2))
        self.assertFalse(blank_input('\x1b[38;2;120;2;2m› user draft\x1b[0m',2))
        self.assertFalse(blank_input('› 1. Resume goal',0))
        self.assertFalse(blank_input('PS workspace> ',2))

    def test_awake_flag_is_released(self):
        awake=Awake()
        with patch('continuous_mode.ctypes.windll.kernel32.SetThreadExecutionState',return_value=1) as call:
            awake.set(True);awake.set(True);awake.set(False)
            self.assertEqual([c.args[0] for c in call.call_args_list],[0x80000001,0x80000000])
