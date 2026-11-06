"""测试异步提问仅入队即返回；后台 worker 负责镜像问题和转交真实答案。"""

import json
from pathlib import Path
import sys
import time
import hashlib
import os
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from codex_user_bridge.config import read_config


def main():
    # Codex 写入 UTF-8；Windows 文本 stdin 可能按本地编码解码并产生代理字符。
    event = json.loads(sys.stdin.buffer.read().decode('utf-8'))
    route = read_config()
    # 统一模式开关：tool 模式完全旁路，hook 只接管异步问题。
    if route['mode'] != 'hook' or event.get('tool_name') != 'request_user_input_async':
        return
    questions = event.get('tool_input', {}).get('questions', [])
    # Hook 可在其他会话被发现，但只处理显式测试标记，避免转发正常会话。
    selected = [q for q in questions if q.get('id') == 'native_bridge_probe'
                or 'native_bridge_probe' in q.get('title', '')]
    control = 'native_bridge_hook_control' in event.get('tool_input', {}).get('command', '')
    if not selected and not control:
        return
    root = Path(__file__).resolve().parents[1]
    out = root / '.local' / 'desktop-hook-events.jsonl'
    out.parent.mkdir(exist_ok=True)
    record = {key: event.get(key) for key in
              ('hook_event_name', 'session_id', 'turn_id', 'tool_use_id', 'tool_name')}
    record['time'] = time.time()
    # 先落盘再访问页面服务，网络错误或字段缺失不能掩盖事件已经触发的事实。
    with out.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({**record, 'stage': 'received'}, ensure_ascii=False) + '\n')
    if selected and event.get('tool_name') == 'request_user_input_async':
        if event.get('hook_event_name') == 'PreToolUse':
            queue = root / '.local' / 'desktop-answer-queue'
            queue.mkdir(exist_ok=True)
            # 使用原数组索引；筛选后的序号会错误关联多问题中的答案。
            for index, question in enumerate(questions):
                if question not in selected:
                    continue
                identity = f"{event['session_id']}:{event['tool_use_id']}:{index}"
                target = queue / (hashlib.sha256(identity.encode()).hexdigest() + '.json')
                job = {'state': 'queued', 'thread_id': event['session_id'],
                       'turn_id': event.get('turn_id'), 'call_id': event['tool_use_id'],
                       'index': index, 'title': question.get('title', question.get('question', '')),
                       'options': [o['label'] if isinstance(o, dict) else o
                                   for o in question.get('options') or []],
                       'expires_at': (time.time() + 3600) * 1000}
                # 路由随问题固化，切换渠道不会把历史本地问题误发到手机。
                job['channel'] = route.get('channel', 'local_chat')
                job['base_url'] = route.get('base_url', 'http://127.0.0.1:5555')
                # 先完整写入临时文件，再原子发布；重复 Hook 不覆盖已消费状态。
                temporary = target.with_suffix(f'.{os.getpid()}.tmp')
                temporary.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
                try:
                    os.link(temporary, target)
                except FileExistsError:
                    pass
                finally:
                    temporary.unlink()
        # PostToolUse 的 accepted 仅代表提问已发出，不能取消等待任务。
        return


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # 只记录异常类型和文本，不输出用户问题或其他会话内容。
        path = Path(__file__).resolve().parents[1] / '.local' / 'desktop-hook-errors.jsonl'
        path.parent.mkdir(exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            detail = exc.read(2048).decode('utf-8', errors='replace') if isinstance(exc, HTTPError) else ''
            stream.write(json.dumps({'time': time.time(), 'error': str(exc), 'detail': detail,
                                     'type': type(exc).__name__}) + '\n')
        raise
