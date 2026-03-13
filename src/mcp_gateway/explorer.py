"""Self-contained MCP Explorer — interactive demo UI for testing all MCP
tools, the OAuth 2.1 flow, and the admin configuration API.

Served at ``/mcp/explorer`` as a single HTML page with zero external
dependencies.  Think of it as "Swagger for MCP".
"""

from __future__ import annotations

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eliza MCP Explorer</title>
<style>
:root{--bg:#f8f9fb;--surface:#fff;--border:#e2e5ea;--text:#1a1d23;--muted:#6b7280;--accent:#6366f1;--accent-hover:#4f46e5;--success:#059669;--error:#dc2626;--code-bg:#f1f3f5;--radius:10px;--shadow:0 1px 3px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.04)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);line-height:1.5}
a{color:var(--accent);text-decoration:none}

/* layout */
.wrapper{max-width:960px;margin:0 auto;padding:1.5rem}
header{display:flex;align-items:center;gap:.75rem;margin-bottom:2rem}
header h1{font-size:1.5rem;font-weight:700}
header .badge{font-size:.7rem;padding:.15rem .5rem;border-radius:20px;background:var(--accent);color:#fff;font-weight:600}

/* auth bar */
.auth-bar{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1rem 1.25rem;margin-bottom:1.5rem;display:flex;gap:.75rem;align-items:end;flex-wrap:wrap;box-shadow:var(--shadow)}
.auth-bar .field{display:flex;flex-direction:column;gap:.2rem;flex:1;min-width:180px}
.auth-bar label{font-size:.75rem;font-weight:600;color:var(--muted)}
.auth-bar input{padding:.5rem .625rem;border:1px solid var(--border);border-radius:6px;font-size:.8125rem;width:100%}
.auth-bar input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(99,102,241,.12)}

/* tabs */
.tabs{display:flex;gap:0;border-bottom:2px solid var(--border);margin-bottom:1.5rem}
.tab{padding:.625rem 1.25rem;font-size:.875rem;font-weight:600;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .15s}
.tab:hover{color:var(--text)}
.tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.tab-panel{display:none}
.tab-panel.active{display:block}

/* cards */
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:1rem;box-shadow:var(--shadow);overflow:hidden}
.card-header{display:flex;align-items:center;justify-content:space-between;padding:.75rem 1rem;cursor:pointer;user-select:none}
.card-header h3{font-size:.9375rem;font-weight:600;display:flex;align-items:center;gap:.5rem}
.card-header .method{font-size:.65rem;padding:.1rem .4rem;border-radius:4px;font-weight:700;text-transform:uppercase}
.method.tool{background:#dbeafe;color:#1d4ed8}
.method.get{background:#dcfce7;color:#166534}
.method.post{background:#fef3c7;color:#92400e}
.method.patch{background:#ede9fe;color:#5b21b6}
.method.delete{background:#fee2e2;color:#991b1b}
.card-header .chevron{transition:transform .2s;font-size:.75rem;color:var(--muted)}
.card-header.open .chevron{transform:rotate(90deg)}
.card-body{display:none;padding:1rem;border-top:1px solid var(--border)}
.card-body.open{display:block}

.field-row{display:flex;gap:.75rem;flex-wrap:wrap;margin-bottom:.75rem}
.field-row .field{flex:1;min-width:200px;display:flex;flex-direction:column;gap:.2rem}
.field-row label{font-size:.75rem;font-weight:600;color:var(--muted)}
.field-row input,.field-row select,.field-row textarea{padding:.5rem .625rem;border:1px solid var(--border);border-radius:6px;font-size:.8125rem;font-family:inherit}
.field-row textarea{min-height:60px;resize:vertical}
.field-row input:focus,.field-row select:focus,.field-row textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(99,102,241,.12)}

.btn{padding:.5rem 1rem;border:none;border-radius:6px;font-size:.8125rem;font-weight:600;cursor:pointer;transition:all .15s}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent-hover)}
.btn-sm{padding:.375rem .75rem;font-size:.75rem}
.btn-danger{background:var(--error);color:#fff}
.btn-danger:hover{background:#b91c1c}

.result-box{margin-top:.75rem;background:var(--code-bg);border-radius:6px;padding:.75rem;font-family:'SF Mono',SFMono-Regular,Consolas,monospace;font-size:.75rem;white-space:pre-wrap;word-break:break-word;max-height:400px;overflow:auto;border:1px solid var(--border)}
.result-box.success{border-left:3px solid var(--success)}
.result-box.error{border-left:3px solid var(--error)}

.status-dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.status-dot.green{background:var(--success)}
.status-dot.red{background:var(--error)}
.status-dot.gray{background:var(--muted)}

.hint{font-size:.75rem;color:var(--muted);margin-bottom:.75rem}
.actions{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}
</style>
</head>
<body>
<div class="wrapper">

<header>
  <h1>Eliza MCP Explorer</h1>
  <span class="badge">Phase 1</span>
  <span id="statusDot" class="status-dot gray" title="Checking..."></span>
</header>

<!-- AUTH BAR -->
<div class="auth-bar">
  <div class="field">
    <label>Base URL</label>
    <input id="baseUrl" value="">
  </div>
  <div class="field">
    <label>Email</label>
    <input id="email" type="email" placeholder="admin@example.com">
  </div>
  <div class="field">
    <label>Password</label>
    <input id="password" type="password" placeholder="password">
  </div>
  <button class="btn btn-primary" onclick="doLogin()">Login &amp; Get Token</button>
  <div class="field" style="flex:2">
    <label>Bearer Token</label>
    <input id="token" placeholder="Paste or login to get one...">
  </div>
</div>

<!-- TABS -->
<div class="tabs">
  <div class="tab active" data-tab="tools">MCP Tools (10)</div>
  <div class="tab" data-tab="oauth">OAuth 2.1</div>
  <div class="tab" data-tab="admin">Admin API</div>
</div>

<!-- ============ TAB: MCP TOOLS ============ -->
<div id="tab-tools" class="tab-panel active">
  <p class="hint">Each tool is called via the MCP Streamable HTTP transport (JSON-RPC POST to <code>/mcp</code>). The Bearer token from above is sent automatically.</p>
  <div id="toolCards"></div>
</div>

<!-- ============ TAB: OAUTH ============ -->
<div id="tab-oauth" class="tab-panel">
  <p class="hint">Test the OAuth 2.1 endpoints that ChatGPT Enterprise uses to authenticate users.</p>

  <div class="card"><div class="card-header" onclick="toggle(this)"><h3><span class="method get">GET</span> Protected Resource Metadata</h3><span class="chevron">&#9654;</span></div>
  <div class="card-body"><p class="hint">RFC 9728 — <code>/.well-known/oauth-protected-resource</code></p>
  <div class="actions"><button class="btn btn-primary btn-sm" onclick="callRest(this,'GET','/mcp/oauth/.well-known/oauth-protected-resource')">Send</button></div>
  <div class="result-box" style="display:none"></div></div></div>

  <div class="card"><div class="card-header" onclick="toggle(this)"><h3><span class="method get">GET</span> Authorization Server Metadata</h3><span class="chevron">&#9654;</span></div>
  <div class="card-body"><p class="hint">RFC 8414 — <code>/.well-known/oauth-authorization-server</code></p>
  <div class="actions"><button class="btn btn-primary btn-sm" onclick="callRest(this,'GET','/mcp/oauth/.well-known/oauth-authorization-server')">Send</button></div>
  <div class="result-box" style="display:none"></div></div></div>

  <div class="card"><div class="card-header" onclick="toggle(this)"><h3><span class="method get">GET</span> Authorize (Login Form)</h3><span class="chevron">&#9654;</span></div>
  <div class="card-body"><p class="hint">Opens the OAuth login page in a new tab.</p>
  <div class="actions"><button class="btn btn-primary btn-sm" onclick="window.open(baseUrl()+'/mcp/oauth/authorize?client_id=demo&redirect_uri='+encodeURIComponent(location.href)+'&code_challenge=test&code_challenge_method=S256&state=demo123','_blank')">Open Login Page</button></div></div></div>

  <div class="card"><div class="card-header" onclick="toggle(this)"><h3><span class="method post">POST</span> Token Exchange</h3><span class="chevron">&#9654;</span></div>
  <div class="card-body">
  <div class="field-row"><div class="field"><label>Authorization Code</label><input id="oauth_code" placeholder="code from callback"></div>
  <div class="field"><label>Code Verifier (PKCE)</label><input id="oauth_verifier" placeholder="original verifier"></div>
  <div class="field"><label>Redirect URI</label><input id="oauth_redirect" placeholder="must match authorize request"></div></div>
  <div class="actions"><button class="btn btn-primary btn-sm" onclick="doTokenExchange(this)">Exchange Code</button></div>
  <div class="result-box" style="display:none"></div></div></div>

  <div class="card"><div class="card-header" onclick="toggle(this)"><h3><span class="method post">POST</span> Refresh Token</h3><span class="chevron">&#9654;</span></div>
  <div class="card-body">
  <div class="field-row"><div class="field"><label>Refresh Token</label><input id="oauth_refresh" placeholder="refresh token"></div></div>
  <div class="actions"><button class="btn btn-primary btn-sm" onclick="doRefreshToken(this)">Refresh</button></div>
  <div class="result-box" style="display:none"></div></div></div>
</div>

<!-- ============ TAB: ADMIN ============ -->
<div id="tab-admin" class="tab-panel">
  <p class="hint">Manage MCP server configurations for your tenant. Requires <code>admin:settings:read</code> / <code>admin:settings:write</code> permissions.</p>

  <div class="card"><div class="card-header" onclick="toggle(this)"><h3><span class="method get">GET</span> List MCP Configs</h3><span class="chevron">&#9654;</span></div>
  <div class="card-body"><div class="actions"><button class="btn btn-primary btn-sm" onclick="callRest(this,'GET','/v1/mcp/admin/configs',null,true)">Send</button></div>
  <div class="result-box" style="display:none"></div></div></div>

  <div class="card"><div class="card-header" onclick="toggle(this)"><h3><span class="method post">POST</span> Create MCP Config</h3><span class="chevron">&#9654;</span></div>
  <div class="card-body">
  <div class="field-row"><div class="field"><label>Server Name</label><input id="cfg_name" value="eliza-chat"></div>
  <div class="field"><label>Display Name</label><input id="cfg_display" placeholder="Acme Chat"></div>
  <div class="field"><label>Server Type</label><select id="cfg_type"><option value="chat">chat</option><option value="applet">applet</option></select></div></div>
  <div class="field-row"><div class="field"><label>Description</label><input id="cfg_desc" placeholder="Optional description"></div>
  <div class="field"><label>Enabled</label><select id="cfg_enabled"><option value="true">Yes</option><option value="false" selected>No</option></select></div></div>
  <div class="actions"><button class="btn btn-primary btn-sm" onclick="createConfig(this)">Create</button></div>
  <div class="result-box" style="display:none"></div></div></div>

  <div class="card"><div class="card-header" onclick="toggle(this)"><h3><span class="method patch">PATCH</span> Toggle Config Enabled</h3><span class="chevron">&#9654;</span></div>
  <div class="card-body"><div class="field-row"><div class="field"><label>Config ID</label><input id="toggle_id" type="number" placeholder="1"></div></div>
  <div class="actions"><button class="btn btn-primary btn-sm" onclick="callRest(this,'POST','/v1/mcp/admin/configs/'+gv('toggle_id')+'/toggle',null,true)">Toggle</button></div>
  <div class="result-box" style="display:none"></div></div></div>

  <div class="card"><div class="card-header" onclick="toggle(this)"><h3><span class="method delete">DELETE</span> Delete Config</h3><span class="chevron">&#9654;</span></div>
  <div class="card-body"><div class="field-row"><div class="field"><label>Config ID</label><input id="del_id" type="number" placeholder="1"></div></div>
  <div class="actions"><button class="btn btn-danger btn-sm" onclick="callRest(this,'DELETE','/v1/mcp/admin/configs/'+gv('del_id'),null,true)">Delete</button></div>
  <div class="result-box" style="display:none"></div></div></div>
</div>

</div><!-- wrapper -->

<script>
// ---- helpers ----
const gv = id => document.getElementById(id).value.trim();
const baseUrl = () => gv('baseUrl') || location.origin;
let _rpcId = 0;
let _mcpSessionId = null; // captured from initialize response header

function toggle(header) {
  header.classList.toggle('open');
  header.nextElementSibling.classList.toggle('open');
}

document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  document.getElementById('tab-' + t.dataset.tab).classList.add('active');
}));

function showResult(btn, data, ok) {
  const box = btn.closest('.card-body').querySelector('.result-box');
  box.style.display = 'block';
  box.className = 'result-box ' + (ok ? 'success' : 'error');
  box.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
}

// ---- login via existing auth API ----
async function doLogin() {
  try {
    const res = await fetch(baseUrl() + '/v1/auth/login', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({email: gv('email'), password: gv('password')})
    });
    const data = await res.json();
    if (data.access_token) {
      document.getElementById('token').value = data.access_token;
      _mcpSessionId = null; // reset so next tool call re-initialises
      _rpcId = 0;
      alert('Token acquired!');
    } else {
      alert('Login failed: ' + JSON.stringify(data));
    }
  } catch(e) { alert('Login error: ' + e.message); }
}

// ---- MCP JSON-RPC helpers ----
function mcpHeaders(token) {
  const h = {'Content-Type':'application/json','Authorization':'Bearer '+token,'Accept':'application/json, text/event-stream'};
  if (_mcpSessionId) h['Mcp-Session-Id'] = _mcpSessionId;
  return h;
}

async function ensureMcpSession(token) {
  if (_mcpSessionId) return true;
  try {
    const res = await fetch(baseUrl()+'/mcp/', {
      method:'POST',
      headers:{'Content-Type':'application/json','Authorization':'Bearer '+token,'Accept':'application/json, text/event-stream'},
      body:JSON.stringify({jsonrpc:'2.0',method:'initialize',params:{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'mcp-explorer',version:'1.0.0'}},id:0})
    });
    const sid = res.headers.get('mcp-session-id');
    if (sid) { _mcpSessionId = sid; return true; }
    return false;
  } catch { return false; }
}

function parseSSEData(text) {
  const lines = text.split('\n');
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      try { return JSON.parse(line.slice(6)); } catch {}
    }
  }
  try { return JSON.parse(text); } catch { return text; }
}

async function callMcpTool(btn, toolName, args) {
  const token = gv('token');
  if (!token) { alert('Enter a Bearer token first.'); return; }
  if (!(await ensureMcpSession(token))) {
    showResult(btn, 'Failed to initialise MCP session. Check token and try again.', false);
    return;
  }
  _rpcId++;
  const body = {jsonrpc:'2.0', method:'tools/call', params:{name:toolName, arguments:args}, id:_rpcId};
  try {
    const res = await fetch(baseUrl()+'/mcp/', {
      method:'POST',
      headers:mcpHeaders(token),
      body:JSON.stringify(body)
    });
    const text = await res.text();
    const data = parseSSEData(text);
    showResult(btn, data, res.ok);
  } catch(e) { showResult(btn, 'Error: ' + e.message, false); }
}

// ---- REST call for admin / OAuth ----
async function callRest(btn, method, path, bodyObj, auth) {
  const opts = {method, headers:{'Content-Type':'application/json'}};
  if (auth) opts.headers['Authorization'] = 'Bearer ' + gv('token');
  if (bodyObj) opts.body = JSON.stringify(bodyObj);
  try {
    const res = await fetch(baseUrl() + path, opts);
    const text = await res.text();
    let data; try { data = JSON.parse(text); } catch { data = text; }
    showResult(btn, data, res.ok);
  } catch(e) { showResult(btn, 'Error: ' + e.message, false); }
}

// ---- OAuth token exchange ----
async function doTokenExchange(btn) {
  const body = {grant_type:'authorization_code', code:gv('oauth_code'), code_verifier:gv('oauth_verifier'), redirect_uri:gv('oauth_redirect')};
  await callRest(btn, 'POST', '/mcp/oauth/token', body, false);
}
async function doRefreshToken(btn) {
  await callRest(btn, 'POST', '/mcp/oauth/token', {grant_type:'refresh_token', refresh_token:gv('oauth_refresh')}, false);
}

// ---- Admin create config ----
async function createConfig(btn) {
  const body = {server_name:gv('cfg_name'), display_name:gv('cfg_display')||null, server_type:gv('cfg_type'), description:gv('cfg_desc')||null, is_enabled:gv('cfg_enabled')==='true'};
  await callRest(btn, 'POST', '/v1/mcp/admin/configs', body, true);
}

// ---- build tool cards ----
const TOOLS = [
  {name:'list_workspaces', desc:'List workspaces the user has access to', fields:[
    {id:'lw_search',label:'Search (optional)',type:'text',arg:'search'},
    {id:'lw_session',label:'Session ID (optional)',type:'text',arg:'session_id'}
  ]},
  {name:'select_workspace', desc:'Set active workspace for the session', fields:[
    {id:'sw_id',label:'Workspace ID',type:'number',arg:'workspace_id',required:true},
    {id:'sw_session',label:'Session ID (optional)',type:'text',arg:'session_id'}
  ]},
  {name:'list_knowledge_bases', desc:'List knowledge bases in the active workspace', fields:[
    {id:'lk_ws',label:'Workspace ID (optional)',type:'number',arg:'workspace_id'},
    {id:'lk_session',label:'Session ID (optional)',type:'text',arg:'session_id'}
  ]},
  {name:'search_documents', desc:'Semantic search across workspace knowledge bases', fields:[
    {id:'sd_q',label:'Query',type:'text',arg:'query',required:true},
    {id:'sd_ws',label:'Workspace ID (optional)',type:'number',arg:'workspace_id'},
    {id:'sd_limit',label:'Limit',type:'number',arg:'limit',default:'10'},
    {id:'sd_session',label:'Session ID (optional)',type:'text',arg:'session_id'}
  ]},
  {name:'chat', desc:'RAG-powered chat within the active workspace', fields:[
    {id:'ch_msg',label:'Message',type:'text',arg:'message',required:true},
    {id:'ch_ws',label:'Workspace ID (optional)',type:'number',arg:'workspace_id'},
    {id:'ch_conv',label:'Conversation ID (optional)',type:'number',arg:'conversation_id'},
    {id:'ch_topk',label:'Top K',type:'number',arg:'top_k',default:'5'},
    {id:'ch_session',label:'Session ID (optional)',type:'text',arg:'session_id'}
  ]},
  {name:'ask_question', desc:'Natural language question against connected data (Text-to-SQL)', fields:[
    {id:'aq_q',label:'Question',type:'text',arg:'question',required:true},
    {id:'aq_co',label:'Company HR Dataset (optional)',type:'text',arg:'company_hr_dataset'},
    {id:'aq_wait',label:'Wait for Result',type:'select',arg:'wait_for_result',options:['false','true']},
    {id:'aq_session',label:'Session ID (optional)',type:'text',arg:'session_id'}
  ]},
  {name:'list_data_connections', desc:'List data connections available to the tenant', fields:[
    {id:'dc_en',label:'Is Enabled',type:'select',arg:'is_enabled',options:['true','false','null']},
    {id:'dc_session',label:'Session ID (optional)',type:'text',arg:'session_id'}
  ]},
  {name:'get_document', desc:'Retrieve a specific document and its chunks', fields:[
    {id:'gd_id',label:'Document ID',type:'number',arg:'document_id',required:true},
    {id:'gd_chunks',label:'Include Chunks',type:'select',arg:'include_chunks',options:['true','false']},
    {id:'gd_limit',label:'Chunk Limit',type:'number',arg:'chunk_limit',default:'20'},
    {id:'gd_session',label:'Session ID (optional)',type:'text',arg:'session_id'}
  ]},
  {name:'upload_document', desc:'Upload a document to a workspace knowledge base', fields:[
    {id:'ud_fn',label:'Filename',type:'text',arg:'filename',required:true},
    {id:'ud_b64',label:'Content (base64)',type:'textarea',arg:'content_base64',required:true},
    {id:'ud_ws',label:'Workspace ID (optional)',type:'number',arg:'workspace_id'},
    {id:'ud_kb',label:'Knowledge Base ID (optional)',type:'number',arg:'knowledge_base_id'},
    {id:'ud_session',label:'Session ID (optional)',type:'text',arg:'session_id'}
  ]},
  {name:'trigger_sync', desc:'Manually trigger a data connection sync', fields:[
    {id:'ts_cid',label:'Connector ID',type:'text',arg:'connector_id',required:true},
    {id:'ts_manual',label:'Manual Trigger',type:'select',arg:'manual_trigger',options:['true','false']},
    {id:'ts_session',label:'Session ID (optional)',type:'text',arg:'session_id'}
  ]}
];

function buildToolCards() {
  const container = document.getElementById('toolCards');
  TOOLS.forEach(tool => {
    const card = document.createElement('div');
    card.className = 'card';
    let fieldsHtml = '<div class="field-row">';
    tool.fields.forEach((f, i) => {
      if (i > 0 && i % 3 === 0) fieldsHtml += '</div><div class="field-row">';
      if (f.type === 'select') {
        const opts = (f.options||[]).map(o => '<option value="'+o+'">'+o+'</option>').join('');
        fieldsHtml += '<div class="field"><label>'+f.label+'</label><select id="'+f.id+'">'+opts+'</select></div>';
      } else if (f.type === 'textarea') {
        fieldsHtml += '<div class="field"><label>'+f.label+'</label><textarea id="'+f.id+'" placeholder="'+(f.required?'required':'optional')+'"></textarea></div>';
      } else {
        fieldsHtml += '<div class="field"><label>'+f.label+'</label><input id="'+f.id+'" type="'+f.type+'" placeholder="'+(f.required?'required':'optional')+'" '+(f.default?'value="'+f.default+'"':'')+'></div>';
      }
    });
    fieldsHtml += '</div>';
    card.innerHTML = `
      <div class="card-header" onclick="toggle(this)">
        <h3><span class="method tool">TOOL</span> ${tool.name}</h3>
        <span class="chevron">&#9654;</span>
      </div>
      <div class="card-body">
        <p class="hint">${tool.desc}</p>
        ${fieldsHtml}
        <div class="actions"><button class="btn btn-primary btn-sm" onclick="execTool(this,'${tool.name}')">Execute</button></div>
        <div class="result-box" style="display:none"></div>
      </div>`;
    container.appendChild(card);
  });
}

function execTool(btn, toolName) {
  const tool = TOOLS.find(t => t.name === toolName);
  const args = {};
  tool.fields.forEach(f => {
    let v = gv(f.id);
    if (!v || v === '') return;
    if (f.type === 'number') { v = parseInt(v, 10); if (isNaN(v)) return; }
    if (v === 'true') v = true;
    if (v === 'false') v = false;
    if (v === 'null') v = null;
    args[f.arg] = v;
  });
  callMcpTool(btn, toolName, args);
}

// ---- init ----
document.getElementById('baseUrl').value = location.origin;
buildToolCards();

(async () => {
  try {
    const r = await fetch(baseUrl()+'/v1/mcp/status');
    const d = await r.json();
    const dot = document.getElementById('statusDot');
    dot.className = 'status-dot ' + (d.ok ? 'green' : 'red');
    dot.title = d.ok ? 'MCP SDK available' : 'MCP SDK unavailable';
  } catch {}
})();
</script>
</body>
</html>"""
