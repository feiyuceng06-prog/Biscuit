// Synthetic loopback only: no credentials, remote host, or provider SDK mock.
import http from 'node:http';
export async function dialogueFixture() {
  const requests = [];
  let releaseRewrite;
  const rewriteAllowed = new Promise(resolve => { releaseRewrite = resolve; });
  const server = http.createServer(async (req, res) => {
    if (req.method !== 'POST' || !req.url.endsWith('/chat/completions')) {
      res.writeHead(404); res.end(); return;
    }
    let raw = ''; for await (const chunk of req) raw += chunk;
    const payload=JSON.parse(raw);
    const prompt=payload.messages?.[0]?.content;
    if (!payload.stream && typeof prompt==='string' && prompt.startsWith('你是 Biscuit 演示文稿编辑')) {
      const layouts=['cover','conclusion','image','comparison','chart','timeline','conclusion','conclusion'];
      const titles=['试点项目进展','核心结论','已交付站点','区域差异','交付进度','交付时间线','备件风险','下季度决策'];
      const content=prompt.includes('页大纲。JSON') ? {title:'试点项目季度汇报',slides:layouts.map((layout,i)=>({layout,title:titles[i]}))}
        : {items:[{label:prompt.includes('重点写延期风险')?'备件风险':'北区',text:'北区已完成 42 个站点，下阶段需优先保障备件。',value:42},
          {label:'南区',text:'南区已完成 28 个站点。',value:28}],notes:'来源：试点项目报告，单位为站点数。'};
      if(prompt.includes('重点写延期风险')) await rewriteAllowed;
      res.writeHead(200,{'Content-Type':'application/json'});
      res.end(JSON.stringify({id:'office',object:'chat.completion',created:0,model:'offline',
        choices:[{index:0,message:{role:'assistant',content:JSON.stringify(content)},finish_reason:'stop'}],
        usage:{prompt_tokens:12,completion_tokens:12,total_tokens:24}})); return;
    }
    requests.push(payload);
    res.writeHead(200, {'Content-Type': 'text/event-stream'});
    const text = `GUI reply ${requests.length} 中文 😀 𠮷`;
    for (const content of [text.slice(0, 12), text.slice(12)]) {
      res.write(`data: ${JSON.stringify({id:'synthetic',object:'chat.completion.chunk',created:0,model:'offline',choices:[{index:0,delta:{content},finish_reason:null}]})}\n\n`);
    }
    res.end(`data: ${JSON.stringify({id:'synthetic',object:'chat.completion.chunk',created:0,model:'offline',choices:[{index:0,delta:{},finish_reason:'stop'}],usage:{prompt_tokens:10,completion_tokens:2,total_tokens:12}})}\n\ndata: [DONE]\n\n`);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return {url:`http://127.0.0.1:${server.address().port}/v1`, requests, releaseRewrite,
    close:() => new Promise(resolve => { server.closeAllConnections(); server.close(resolve); })};
}
