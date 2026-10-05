// Test-only TLS boundary. Binds localhost; never forwards to a public host.
const https = require('node:https'), http = require('node:http'), fs = require('node:fs');
const server = https.createServer({key:fs.readFileSync(process.env.FORTUNE_TEST_TLS_KEY),cert:fs.readFileSync(process.env.FORTUNE_TEST_TLS_CERT)},(req,res)=>{
 const headers={...req.headers, host:'app.hakase-uranai.jp', 'x-real-ip':req.socket.remoteAddress,
  'x-forwarded-for':req.socket.remoteAddress, 'x-forwarded-proto':'https', 'x-forwarded-host':'app.hakase-uranai.jp'};
 delete headers.forwarded;
 const upstream=http.request({hostname:'127.0.0.1',port:req.url.startsWith('/api/')?8765:3000,path:req.url,method:req.method,headers},reply=>{
  res.writeHead(reply.statusCode,reply.headers);reply.pipe(res);
 });
 upstream.on('error',()=>{res.writeHead(502);res.end('Local test upstream unavailable');});req.pipe(upstream);
});
server.listen(443,'127.0.0.1');
