import test from 'node:test';
import assert from 'node:assert/strict';
import {advance} from '../scripts/desktop_answer_worker.mjs';

function fixture(overrides = {}) {
  const states = [], sent = [];
  const job = {state:'queued', expires_at:9999, thread_id:'thread', call_id:'call', index:2, title:'question', options:[]};
  const deps = {now:()=>1, save:async j=>states.push(j.state),
    request:async endpoint => endpoint === '/health' ? {channel:'local_chat'} :
      endpoint === '/chat' ? {question_id:'q1'} : {status:'answered', reply:{text:'测试答案', is_simulated:false}},
    send:async (j, text)=>{sent.push(text); return {success:true};}, ...overrides};
  return {job, deps, states, sent};
}

test('答案到达后先保存 sending，成功只标记 submitted，重复轮询不重发', async()=>{
  const f = fixture(); await advance(f.job, f.deps); await advance(f.job, f.deps);
  assert.deepEqual(f.states, ['waiting','sending','submitted']);
  assert.equal(f.sent.length, 1); assert.match(f.sent[0], /问题索引：2/);
});
test('提交异常和发送中重启均保留 unknown，不自动重发', async()=>{
  const f = fixture({send:async()=>{throw new Error('断线');}});
  await advance(f.job, f.deps); assert.equal(f.job.state, 'unknown');
  f.job.state = 'sending'; await advance(f.job, f.deps);
  assert.equal(f.job.state, 'unknown');
});
test('pending 不阻塞单轮处理，也不调用发送', async()=>{
  const f = fixture({request:async()=>({status:'pending'})});
  f.job.state = 'waiting'; await advance(f.job, f.deps);
  assert.equal(f.job.state, 'waiting'); assert.equal(f.sent.length, 0);
});
test('拒绝模拟答案', async()=>{
  const f = fixture({request:async()=>({status:'answered',reply:{text:'fake',is_simulated:true}})});
  f.job.state = 'waiting'; await advance(f.job, f.deps);
  assert.equal(f.job.state, 'failed'); assert.equal(f.sent.length, 0);
});
test('过期任务不转交，桌面拒绝不标记成功', async()=>{
  const f = fixture(); f.job.expires_at=0; await advance(f.job, f.deps);
  assert.equal(f.job.state, 'expired'); assert.equal(f.sent.length, 0);
  const g = fixture({send:async()=>({success:false})}); await advance(g.job,g.deps);
  assert.equal(g.job.state,'failed');
});
