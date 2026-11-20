// Synthetic loopback only: no credentials, remote host, or provider SDK mock.
import http from 'node:http';
export async function dialogueFixture() {
  const requests = [];
  const server = http.createServer(async (req, res) => {
    if (req.method !== 'POST' || !req.url.endsWith('/chat/completions')) {
      res.writeHead(404); res.end(); return;
    }
    let raw = ''; for await (const chunk of req) raw += chunk;
    requests.push(JSON.parse(raw));
    res.writeHead(200, {'Content-Type': 'text/event-stream'});
    const text = `GUI reply ${requests.length} 中文 😀 𠮷`;
    for (const content of [text.slice(0, 12), text.slice(12)]) {
      res.write(`data: ${JSON.stringify({id:'synthetic',object:'chat.completion.chunk',created:0,model:'offline',choices:[{index:0,delta:{content},finish_reason:null}]})}\n\n`);
    }
    res.end(`data: ${JSON.stringify({id:'synthetic',object:'chat.completion.chunk',created:0,model:'offline',choices:[{index:0,delta:{},finish_reason:'stop'}],usage:{prompt_tokens:10,completion_tokens:2,total_tokens:12}})}\n\ndata: [DONE]\n\n`);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return {url:`http://127.0.0.1:${server.address().port}/v1`, requests,
    close:() => new Promise(resolve => { server.closeAllConnections(); server.close(resolve); })};
}
