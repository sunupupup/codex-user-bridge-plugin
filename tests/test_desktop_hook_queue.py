"""Hook 只落盘，不需要本地 HTTP 服务；重复调用不能覆盖消费状态。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class DesktopHookQueueTest(unittest.TestCase):
    def test_original_index_and_duplicate_preserve_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            script = root / 'scripts/desktop_hook_probe.py'
            shutil.copyfile(Path(__file__).resolve().parents[1] / 'scripts/desktop_hook_probe.py', script)
            config = root / 'config.json'
            config.write_text(json.dumps({'mode':'hook','channel':'local_chat','base_url':'http://127.0.0.1:5555'}))
            event = {'tool_name': 'request_user_input_async', 'hook_event_name': 'PreToolUse',
                     'session_id': 'test', 'turn_id': 'turn', 'tool_use_id': 'call',
                     'tool_input': {'questions': [{'title': '不转交'}, {'title': 'native_bridge_probe：中文测试'}]}}
            def run():
                subprocess.run([sys.executable, str(script)],
                               input=json.dumps(event, ensure_ascii=False).encode('utf-8'),
                               check=True, timeout=3, capture_output=True,
                               env={**os.environ, 'BRIDGE_CONFIG':str(config)})
            run()
            files = list((root / '.local/desktop-answer-queue').glob('*.json'))
            self.assertEqual(len(files), 1)
            job = json.loads(files[0].read_text(encoding='utf-8'))
            self.assertEqual(job['index'], 1)
            self.assertEqual(job['title'], 'native_bridge_probe：中文测试')
            job['state'] = 'submitted'
            files[0].write_text(json.dumps(job), encoding='utf-8')
            run()
            event['hook_event_name'] = 'PostToolUse'
            run()
            self.assertEqual(json.loads(files[0].read_text())['state'], 'submitted')
            # mode 切换后不再为新调用创建后台任务。
            config.write_text(json.dumps({'mode':'tool','channel':'local_chat','base_url':'http://127.0.0.1:5555'}))
            event['hook_event_name'] = 'PreToolUse'
            event['tool_use_id'] = 'another-call'
            run()
            self.assertEqual(len(list(files[0].parent.glob('*.json'))), 1)


if __name__ == '__main__':
    unittest.main()
