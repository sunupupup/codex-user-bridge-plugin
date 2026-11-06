/** 实验适配：只转交本地真实回复，不把发送成功解释为原生卡片关闭。 */
import net from 'node:net';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const queueDir = fileURLToPath(new URL('../.local/desktop-answer-queue/', import.meta.url));

export function rpc(method, params, pipe = process.env.CODEX_APP_TOOLS_PIPE_PATH) {
  if (!pipe) return Promise.reject(new Error('请从 Codex 环境启动：缺少桌面通信管道'));
  return new Promise((resolve, reject) => {
    const socket = net.createConnection(pipe);
    let buffer = Buffer.alloc(0);
    const timer = setTimeout(() => finish(new Error('桌面请求超时，结果未知')), 15000);
    function finish(error, result) {
      clearTimeout(timer); socket.destroy();
      error ? reject(error) : resolve(result);
    }
    socket.on('error', finish);
    socket.on('end', () => finish(new Error('桌面连接结束，结果未知')));
    socket.on('connect', () => {
      const body = Buffer.from(JSON.stringify({jsonrpc:'2.0', id:1, method, params}));
      const header = Buffer.alloc(4); header.writeUInt32LE(body.length);
      socket.write(Buffer.concat([header, body]));
    });
    socket.on('data', chunk => {
      buffer = Buffer.concat([buffer, chunk]);
      if (buffer.length < 4) return;
      const size = buffer.readUInt32LE();
      if (size > 8 * 1024 * 1024) return finish(new Error('桌面响应过大'));
      if (buffer.length < size + 4) return;
      try {
        const message = JSON.parse(buffer.subarray(4, size + 4));
        if (message.error) finish(new Error(message.error.message));
        else finish(null, message.result);
      } catch (error) { finish(error); }
    });
  });
}

export function replyPrompt(job, answer) {
  // 明确来源与关联编号；不用伪造原生答案标签冒充桌面提交。
  return `用户通过 ${job.channel || 'local_chat'} 回复了先前的异步提问。请将以下文本作为该问题的用户回复继续处理。\n` +
    `原调用：${job.call_id}；问题索引：${job.index}；本地问题：${job.question_id}\n` +
    `原问题：${job.title}\n用户回复：${JSON.stringify(answer)}\n` +
    `这是本地答案转交，不表示原生提问卡片已关闭。`;
}

async function http(endpoint, body, base = 'http://127.0.0.1:5555') {
  const url = new URL(base);
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new Error('只允许本机服务地址');
  const response = await fetch(base + endpoint, {
    signal: AbortSignal.timeout(3000),
    ...(body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {})
  });
  if (!response.ok) throw new Error(`本地服务 HTTP ${response.status}`);
  return response.json();
}

export async function advance(job, {save, request = (endpoint, body) => http(endpoint, body, job.base_url), send, now = Date.now}) {
  if (['submitted','unknown','expired','failed'].includes(job.state)) return;
  // 发送前先持久化。重启遇到 sending 不能盲目重发，否则会重复唤醒聊天。
  if (job.state === 'sending') { job.state = 'unknown'; await save(job); return; }
  if (now() > job.expires_at) { job.state = 'expired'; await save(job); return; }
  if (job.state === 'queued') {
    const health = await request('/health');
    const channel = job.channel || 'local_chat';
    if (!['local_chat', 'telegram'].includes(channel) || health.channel !== channel) throw new Error('服务渠道与问题绑定渠道不一致');
    const result = await request('/chat', {
      task_id:job.thread_id, request_id:`desktop-relay:${job.call_id}:${job.index}`,
      message:`[后台答案转交测试] ${job.title}`, options:job.options
    });
    job.question_id = result.question_id; job.state = 'waiting'; await save(job);
  }
  const result = await request(`/chat/${encodeURIComponent(job.question_id)}?task_id=${encodeURIComponent(job.thread_id)}`);
  if (result.status !== 'answered' || !result.reply) return;
  if (result.reply.is_simulated !== false || typeof result.reply.text !== 'string' ||
      (job.channel === 'telegram' && result.reply.source !== 'telegram')) {
    job.state = 'failed'; job.error = '拒绝模拟答案或无效回复'; await save(job); return;
  }
  job.state = 'sending'; await save(job);
  try {
    const receipt = await send(job, replyPrompt(job, result.reply.text));
    // API 接受与模型已阅读分开：最终验收还要看目标聊天的回应。
    job.state = receipt.success === true ? 'submitted' : 'failed';
    job.receipt = receipt;
  } catch (error) { job.state = 'unknown'; job.error = error.message; }
  await save(job);
}

async function main() {
  const catalog = await rpc('tools/list', {threadStartKind:'all'});
  const tool = catalog.tools.find(t => t.name === 'send_message_to_thread');
  if (!tool) throw new Error('当前桌面没有 send_message_to_thread');
  if (process.argv.includes('--check')) { console.log('桌面转交工具可用'); return; }
  await fs.mkdir(queueDir, {recursive:true});
  const lockPath = path.join(queueDir, 'worker.lock');
  // 锁文件残留时明确报错，由操作者核对旧进程，避免两个 worker 同时消费。
  const lock = await fs.open(lockPath, 'wx');
  await lock.writeFile(String(process.pid));
  let stop = false;
  process.on('SIGINT', () => { stop = true; });
  process.on('SIGTERM', () => { stop = true; });
  console.log('后台答案队列已启动，每 2 秒检查；Ctrl+C 停止');
  try {
    while (!stop) {
      for (const name of await fs.readdir(queueDir)) {
        if (!name.endsWith('.json')) continue;
        const filename = path.join(queueDir, name);
        try {
          const job = JSON.parse(await fs.readFile(filename, 'utf8'));
          await advance(job, {
            save: async value => {
              await fs.writeFile(filename + '.tmp', JSON.stringify(value, null, 2));
              await fs.rename(filename + '.tmp', filename);
            },
            send: (value, prompt) => rpc('tools/call', {
              namespace:tool.namespace, tool:tool.name,
              callerSource:'codex', hostId:process.env.CODEX_APP_TOOLS_CALLER_HOST_ID,
              threadId:value.thread_id, turnId:value.turn_id, callId:value.call_id,
              arguments:{hostId:'local', threadId:value.thread_id, prompt}
            })
          });
        } catch (error) { console.error(name, error.message); }
      }
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  } finally { await lock.close(); await fs.unlink(lockPath); }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
