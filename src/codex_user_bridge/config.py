"""命令行与运行时共享配置；配置留在用户目录，不随插件缓存升级丢失。"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from contextlib import closing

from .adapters import LocalHttpAdapter

PORTS = {'local_chat': 5555, 'telegram': 5556, 'local_mock': 5555,
         'feishu': 5557, 'weixin': 5558}


def config_path():
    return Path(os.environ.get('BRIDGE_CONFIG') or
                Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'user-bridge/config.json')


def validate(value):
    if set(value) - {'mode', 'channel', 'base_url'}:
        raise ValueError('只支持 mode、channel、base_url')
    if value.get('mode') not in ('tool', 'hook') or value.get('channel') not in PORTS:
        raise ValueError('mode 必须是 tool/hook，channel 必须是已支持渠道')
    if value['mode'] == 'hook' and value['channel'] not in ('local_chat', 'telegram', 'weixin'):
        raise ValueError('hook 模式仅支持 local_chat/telegram/weixin；请先切换渠道')
    LocalHttpAdapter(value['base_url'])
    return value


def read_config():
    path = config_path()
    if path.exists():
        return validate(json.loads(path.read_text(encoding='utf-8-sig')))
    return {'mode': 'tool', 'channel': 'local_chat',
            'base_url': os.environ.get('BRIDGE_BASE_URL', 'http://127.0.0.1:5555')}


def set_config(key, value):
    config = read_config()
    if key not in ('mode', 'channel', 'base_url'):
        raise ValueError('只支持 mode、channel、base_url')
    config[key] = value
    if key == 'channel' and value in PORTS:
        config['base_url'] = f'http://127.0.0.1:{PORTS[value]}'
    validate(config)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # 原子替换避免 Hook 恰好读取到写了一半的 JSON。
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(config, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return config


def route(task, request=None, question=None, bind=None):
    """发送前绑定请求地址，超时重试和切换渠道后查询都沿用原地址。"""
    path = config_path().with_name('tool-routes.sqlite3')
    path.parent.mkdir(parents=True, exist_ok=True)
    # sqlite 事务上下文不会关闭连接；显式关闭，避免 Windows 持续占用数据库。
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS routes (task TEXT, request TEXT, question TEXT, url TEXT, PRIMARY KEY(task,request))')
        if bind is not None:
            db.execute('INSERT OR IGNORE INTO routes VALUES (?,?,NULL,?)', (task, request, bind))
        if request is not None and question is not None:
            db.execute('UPDATE routes SET question=? WHERE task=? AND request=?', (question, task, request))
        if request is not None:
            row = db.execute('SELECT url FROM routes WHERE task=? AND request=?', (task, request)).fetchone()
        else:
            row = db.execute('SELECT url FROM routes WHERE task=? AND question=?', (task, question)).fetchone()
        return row[0] if row else None


def main():
    parser = argparse.ArgumentParser(description='Bridge 用户配置；不修改密钥，不自动启动服务')
    sub = parser.add_subparsers(dest='command', required=True)
    cfg = sub.add_parser('config').add_subparsers(dest='action', required=True)
    cfg.add_parser('show')
    setter = cfg.add_parser('set')
    setter.add_argument('key', choices=['mode', 'channel', 'base_url'])
    setter.add_argument('value')
    args = parser.parse_args()
    try:
        config = set_config(args.key, args.value) if args.action == 'set' else read_config()
        print(json.dumps({'config_file': str(config_path()), **config}, ensure_ascii=False, indent=2))
        if args.action == 'set':
            print('配置已保存，新问题按新配置处理；请确保对应渠道服务已启动。')
    except (ValueError, OSError) as exc:
        parser.exit(2, f'配置错误：{exc}\n')


if __name__ == '__main__':
    main()
