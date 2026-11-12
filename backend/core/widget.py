"""Serves the default embeddable chat widget as a self-contained vanilla-JS file."""
from django.http import HttpResponse

WIDGET_JS = r"""
(function() {
  var script = document.currentScript;
  var apiKey = script.getAttribute('data-api-key');
  var apiBase = (script.getAttribute('data-api-base') || new URL(script.src).origin).replace(/\/$/, '');
  if (!apiKey) { console.error('[SupportAgentAI widget] data-api-key is required.'); return; }

  var state = { token: null, bot: null };

  function el(tag, attrs, children) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) {
      if (k === 'style') e.style.cssText = attrs[k];
      else if (k.indexOf('on') === 0) e.addEventListener(k.slice(2), attrs[k]);
      else e.setAttribute(k, attrs[k]);
    }
    (children || []).forEach(function(c) { e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return e;
  }

  var launcher = el('button', { style:
    'position:fixed;bottom:20px;right:20px;width:60px;height:60px;border-radius:50%;' +
    'background:#2b45f5;color:#fff;border:none;box-shadow:0 8px 24px rgba(0,0,0,.25);' +
    'cursor:pointer;font-size:26px;z-index:999999;line-height:1;'
  }, ['\uD83D\uDCAC']);

  var panel = el('div', { style:
    'position:fixed;bottom:92px;right:20px;width:340px;max-width:92vw;height:480px;max-height:70vh;' +
    'background:#fff;border-radius:16px;box-shadow:0 16px 48px rgba(0,0,0,.28);display:none;' +
    'flex-direction:column;overflow:hidden;z-index:999999;font-family:system-ui,-apple-system,sans-serif;'
  });

  var header = el('div', { style: 'padding:14px 16px;background:#2b45f5;color:#fff;font-weight:700;' +
    'display:flex;justify-content:space-between;align-items:center;flex-shrink:0;' });
  var headerTitle = el('span', {}, ['Chat']);
  var closeBtn = el('button', { style: 'background:none;border:none;color:#fff;font-size:20px;cursor:pointer;line-height:1;', onclick: togglePanel }, ['\u00D7']);
  header.appendChild(headerTitle); header.appendChild(closeBtn);

  var body = el('div', { style: 'flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:#f2f4f1;' });
  var formArea = el('div', { style: 'padding:12px;border-top:1px solid #eee;flex-shrink:0;' });

  panel.appendChild(header); panel.appendChild(body); panel.appendChild(formArea);
  document.body.appendChild(panel);
  document.body.appendChild(launcher);
  launcher.addEventListener('click', togglePanel);

  function togglePanel() {
    var open = panel.style.display !== 'flex';
    panel.style.display = open ? 'flex' : 'none';
    if (open && !state.token && !formArea.dataset.loading) renderLeadForm();
  }

  function inputStyle() { return 'width:100%;padding:8px 10px;border:1px solid #ddd;border-radius:8px;font:inherit;box-sizing:border-box;'; }
  function btnStyle() { return 'width:100%;margin-top:8px;padding:10px;border:none;border-radius:8px;background:#2b45f5;color:#fff;font-weight:600;cursor:pointer;'; }

  function renderLeadForm() {
    formArea.dataset.loading = '1';
    formArea.innerHTML = '';
    var name = el('input', { placeholder: 'Your name', style: inputStyle() });
    var email = el('input', { placeholder: 'Your email', type: 'email', style: inputStyle() + 'margin-top:8px;' });
    var btn = el('button', { style: btnStyle(), onclick: function() { connect(name.value.trim(), email.value.trim()); } }, ['Start chat']);
    formArea.appendChild(name); formArea.appendChild(email); formArea.appendChild(btn);
  }

  function connect(name, email) {
    if (!name || !email) return;
    fetch(apiBase + '/api/public/token/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
      body: JSON.stringify({ origin: window.location.origin, name: name, email: email })
    }).then(function(r) { return r.json().then(function(d) { if (!r.ok) throw new Error(d.message || 'Could not connect.'); return d; }); })
      .then(function(data) {
        state.token = data.visitor_token;
        state.bot = data.bot;
        headerTitle.textContent = data.bot.name || 'Chat';
        renderChatInput();
        addMessage('assistant', data.bot.greeting);
        if (data.bot.starter_questions && data.bot.starter_questions.length) renderStarters(data.bot.starter_questions);
      })
      .catch(function(err) {
        formArea.insertBefore(el('div', { style: 'color:#b91c1c;font-size:13px;margin-bottom:6px;' }, [err.message]), formArea.firstChild);
        formArea.dataset.loading = '';
      });
  }

  function renderChatInput() {
    formArea.innerHTML = '';
    var input = el('input', { placeholder: 'Type your question...', style: inputStyle() });
    var send = el('button', { style: btnStyle(), onclick: function() { var v = input.value.trim(); if (v) { input.value = ''; sendMessage(v); } } }, ['Send']);
    input.addEventListener('keydown', function(e) { if (e.key === 'Enter') send.click(); });
    formArea.appendChild(input); formArea.appendChild(send);
  }

  function renderStarters(questions) {
    var wrap = el('div', { style: 'display:flex;flex-wrap:wrap;gap:6px;margin-top:4px;' });
    questions.forEach(function(q) {
      wrap.appendChild(el('button', {
        style: 'padding:6px 10px;border:1px solid #ddd;border-radius:999px;background:#fff;font-size:12px;cursor:pointer;',
        onclick: function() { sendMessage(q); }
      }, [q]));
    });
    body.appendChild(wrap);
  }

  function addMessage(role, text) {
    var bubble = el('div', { style:
      'max-width:85%;padding:8px 12px;border-radius:12px;font-size:14px;line-height:1.45;white-space:pre-wrap;word-break:break-word;' +
      (role === 'user' ? 'align-self:flex-end;background:#2b45f5;color:#fff;' : 'align-self:flex-start;background:#fff;border:1px solid #ddd;')
    }, [text]);
    body.appendChild(bubble);
    body.scrollTop = body.scrollHeight;
    return bubble;
  }

  function sendMessage(text) {
    addMessage('user', text);
    var bubble = addMessage('assistant', '\u2026');
    fetch(apiBase + '/api/public/chat/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + state.token },
      body: JSON.stringify({ content: text })
    }).then(function(response) {
      if (!response.ok) return response.json().then(function(d) { throw new Error(d.message || 'Something went wrong.'); });
      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';
      var full = '';
      function read() {
        return reader.read().then(function(res) {
          if (res.done) return;
          buffer += decoder.decode(res.value, { stream: true });
          var idx;
          while ((idx = buffer.indexOf('\n\n')) !== -1) {
            var block = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            var eventName = 'message', data = '';
            block.split('\n').forEach(function(line) {
              if (line.indexOf('event:') === 0) eventName = line.slice(6).trim();
              else if (line.indexOf('data:') === 0) data += line.slice(5).trim();
            });
            if (!data) continue;
            var payload;
            try { payload = JSON.parse(data); } catch (e) { continue; }
            if (eventName === 'token') { full += payload.text; bubble.textContent = full; body.scrollTop = body.scrollHeight; }
            else if (eventName === 'done') { bubble.textContent = payload.text; }
            else if (eventName === 'error') { bubble.textContent = payload.message; bubble.style.color = '#b91c1c'; }
          }
          return read();
        });
      }
      return read();
    }).catch(function(err) { bubble.textContent = err.message; bubble.style.color = '#b91c1c'; });
  }
})();
"""


def widget_js(request):
    response = HttpResponse(WIDGET_JS, content_type="application/javascript; charset=utf-8")
    response["Cache-Control"] = "public, max-age=300"
    return response