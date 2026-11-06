"""隔离用户配置，验证模式切换与旧任务的路由，不发送外部消息。"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_user_bridge.config import read_config, set_config, route
from codex_user_bridge import mcp_server


class ConfigTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'config.json'
        self.env = patch.dict(os.environ, {'BRIDGE_CONFIG':str(self.path)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_validate_and_preserve(self):
        self.assertEqual(read_config()['mode'], 'tool')
        set_config('channel', 'telegram')
        set_config('mode', 'hook')
        before = self.path.read_bytes()
        for key, value in [('mode','bad'), ('channel','weixin'), ('base_url','https://example.com')]:
            with self.assertRaises(ValueError): set_config(key,value)
            self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(read_config()['base_url'], 'http://127.0.0.1:5556')

    async def test_hook_rejects_tools_but_drains_known_reply(self):
        set_config('mode','hook')
        with self.assertRaises(ValueError):
            await mcp_server.bridge_send_question('t','r','question',[])
        with self.assertRaises(ValueError):
            await mcp_server.bridge_get_reply('t','unknown')
        route('t',request='r',bind='http://127.0.0.1:5555')
        route('t',request='r',question='q')
        # 确认校验后确实尝试旧地址，而不是被模式拦截或改用新地址。
        async def reply(adapter, task, question):
            self.assertEqual(adapter.base_url,'http://127.0.0.1:5555')
            raise RuntimeError('old-route-used')
        set_config('channel','telegram')
        with patch.object(mcp_server.LocalHttpAdapter,'get_reply',reply):
            with self.assertRaisesRegex(RuntimeError,'old-route-used'):
                await mcp_server.bridge_get_reply('t','q')

    def test_retry_keeps_original_route(self):
        route('t',request='r',bind='http://127.0.0.1:5555')
        self.assertEqual(route('t',request='r',bind='http://127.0.0.1:5556'), 'http://127.0.0.1:5555')
        route('t',request='r',question='q')
        self.assertEqual(route('t',question='q'),'http://127.0.0.1:5555')
        self.assertIsNone(route('other',question='q'))
