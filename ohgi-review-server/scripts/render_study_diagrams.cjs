// Local-only Mermaid renderer. No CDN or external page requests are used.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const runtime = process.env.CODEX_NODE_MODULES || 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1112-737-0_26.1112.737.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules';
const { chromium } = require(path.join(runtime, 'playwright'));
const mermaidRoot = process.env.MERMAID_DIST || 'C:/myLectureWs/.diagram-tools/security-flow-preview/node_modules/mermaid/dist';
const root = path.resolve(__dirname, '../docs/study');
const diagramRoot = path.join(root, 'diagrams');
const output = path.join(root, 'assets');
fs.mkdirSync(output, { recursive: true });
const html = `<!doctype html><meta charset="utf-8"><style>
body{margin:0;background:#101b2e;font-family:'Malgun Gothic',sans-serif}#chart{display:inline-block;padding:24px;background:#101b2e}
.edgeLabel p{background:#101b2e!important;color:#e5edf8!important}.nodeLabel{color:#edf3fb!important}
</style><div id="chart"></div><script type="module">
import mermaid from '/mermaid/mermaid.esm.min.mjs';
mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'base',fontFamily:'Malgun Gothic',
 themeVariables:{darkMode:true,background:'#101b2e',primaryColor:'#15344a',primaryTextColor:'#edf3fb',primaryBorderColor:'#5dc9d7',secondaryColor:'#24304d',tertiaryColor:'#102134',lineColor:'#8acfe8',textColor:'#edf3fb',edgeLabelBackground:'#101b2e',clusterBkg:'#101b2e',clusterBorder:'#354d6b',fontSize:'20px'},
 flowchart:{htmlLabels:true,curve:'basis',nodeSpacing:32,rankSpacing:38,padding:18,subGraphTitleMargin:{top:12,bottom:20}}});
window.renderChart=async(name)=>{const code=await(await fetch('/source/'+name)).text();const rendered=await mermaid.render('diagram-'+name.replaceAll('.','-'),code);document.querySelector('#chart').innerHTML=rendered.svg;await document.fonts.ready;const svg=document.querySelector('svg');const b=svg.viewBox.baseVal;svg.style.maxWidth='none';svg.style.width=b.width+'px';svg.style.height=b.height+'px';return {width:b.width,height:b.height,nodes:document.querySelectorAll('.node').length};};
</script>`;
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  if (url.pathname === '/') { res.writeHead(200, {'Content-Type':'text/html;charset=utf-8'}); return res.end(html); }
  let file;
  if (url.pathname.startsWith('/mermaid/')) file = path.resolve(mermaidRoot, url.pathname.slice(9));
  else if (/^\/source\/[a-z0-9_]+\.mmd$/.test(url.pathname)) file = path.join(diagramRoot, path.basename(url.pathname));
  const allowed = file && (file.startsWith(path.resolve(mermaidRoot)+path.sep) || file.startsWith(diagramRoot+path.sep));
  if (!allowed || !fs.existsSync(file)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, {'Content-Type':file.endsWith('.mmd')?'text/plain;charset=utf-8':'text/javascript'});
  fs.createReadStream(file).pipe(res);
});
(async()=>{
  let browser;
  try {
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    const page=await browser.newPage({viewport:{width:2600,height:2000},deviceScaleFactor:2});
    await page.goto('http://127.0.0.1:'+server.address().port,{waitUntil:'networkidle'});
    await page.waitForFunction(()=>typeof window.renderChart==='function');
    const manifest=[];
    for (const name of fs.readdirSync(diagramRoot).filter(x=>x.endsWith('.mmd')).sort()) {
      const size=await page.evaluate(name=>window.renderChart(name),name);
      const svg=await page.locator('#chart svg').evaluate(el=>el.outerHTML);
      fs.writeFileSync(path.join(output,name.replace('.mmd','.svg')),svg);
      await page.locator('#chart').screenshot({path:path.join(output,name.replace('.mmd','.png'))});
      manifest.push({name,...size});
    }
    fs.writeFileSync(path.join(root,'diagram_manifest.json'),JSON.stringify(manifest,null,2));
    process.stdout.write(JSON.stringify({rendered:manifest.length,assets:output}));
  } finally { if(browser)await browser.close();server.close(); }
})().catch(err=>{process.stderr.write(err.stack);process.exitCode=1;});
