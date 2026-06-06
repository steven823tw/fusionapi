"""Generate self-contained HTML files: FULLY OFFLINE (default) and ONLINE (CDN) variants.

Both embed all 5 OpenAPI specs as base64 data URLs and BCManager markdown as JSON.
The offline version inlines Swagger UI CSS/JS and markdown-it JS so it works without
any network connection.
"""
import base64
import json
import yaml
from pathlib import Path

ROOT = Path(r"C:\Users\steven\Desktop\fusion\fusion-swagger")
STATIC = ROOT / "_static"
OUT_OFFLINE = ROOT / "FusionCompute-API-OFFLINE.html"
OUT_ONLINE  = ROOT / "FusionCompute-API-ONLINE.html"

SPECS = [
    {'id': 'vrm',       'name': 'VRM (454)',            'file': 'vrm.yaml',     'kind': 'openapi'},
    {'id': 'container', 'name': 'Container (185)',      'file': 'container.yaml','kind': 'openapi'},
    {'id': 'as',        'name': 'AutoScaling (20)',    'file': 'as.yaml',      'kind': 'openapi'},
    {'id': 'image',     'name': 'Image (35, v8.8/8.9)','file': 'image.yaml',   'kind': 'openapi'},
    {'id': 'kms',       'name': 'KMS (22)',             'file': 'kms.yaml',     'kind': 'openapi'},
    {'id': 'bcmanager', 'name': 'BCManager Socket (5)','file': 'BCManager-Socket-Protocol.md', 'kind': 'markdown'},
]


def make_data_url(yaml_text):
    b64 = base64.b64encode(yaml_text.encode('utf-8')).decode('ascii')
    return f'data:application/yaml;base64,{b64}'


def build_swagger_urls():
    urls = []
    for spec in SPECS:
        if spec['kind'] != 'openapi':
            continue
        yaml_text = (ROOT / spec['file']).read_text(encoding='utf-8')
        urls.append({'name': spec['name'], 'url': make_data_url(yaml_text)})
    return urls


def build_md_payloads():
    out = {}
    for spec in SPECS:
        if spec['kind'] != 'markdown':
            continue
        out[spec['id']] = (ROOT / spec['file']).read_text(encoding='utf-8')
    return out


def total_paths():
    n = 0
    for spec in SPECS:
        if spec['kind'] != 'openapi':
            continue
        with open(ROOT / spec['file'], encoding='utf-8') as f:
            n += len(yaml.safe_load(f).get('paths', {}))
    return n


# Common template (uses .format() with {placeholders}, CSS/JS blocks are injected)
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{title}</title>
{css_block}
<style>
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; }}
  .topbar {{
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    color: #fff; padding: 14px 20px;
    display: flex; align-items: center; gap: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    position: sticky; top: 0; z-index: 100;
  }}
  .topbar h1 {{ margin: 0; font-size: 1.25em; font-weight: 600; }}
  .topbar .meta {{ color: rgba(255,255,255,0.85); font-size: 0.85em; margin-left: auto; }}
  .tabs {{ display: flex; gap: 6px; margin-left: 12px; flex-wrap: wrap; }}
  .tab {{
    background: rgba(255,255,255,0.1); color: #fff;
    border: 1px solid rgba(255,255,255,0.2);
    padding: 6px 14px; border-radius: 6px; cursor: pointer;
    font-size: 0.88em; transition: all 0.15s;
  }}
  .tab:hover {{ background: rgba(255,255,255,0.2); }}
  .tab.active {{ background: #fff; color: #1e3c72; border-color: #fff; font-weight: 600; }}
  #swagger-ui {{ display: none; }}
  #swagger-ui.active {{ display: block; }}
  #md-view {{ display: none; padding: 30px 40px; max-width: 1100px; margin: 0 auto; }}
  #md-view.active {{ display: block; }}
  #md-view h1 {{ color: #1e3c72; border-bottom: 3px solid #2a5298; padding-bottom: 10px; }}
  #md-view h2 {{ color: #2a5298; border-bottom: 1px solid #ddd; padding-bottom: 6px; margin-top: 36px; }}
  #md-view h3 {{ color: #444; margin-top: 22px; }}
  #md-view table {{ border-collapse: collapse; width: 100%; margin: 14px 0; }}
  #md-view th, #md-view td {{ border: 1px solid #d0d0d0; padding: 8px 12px; text-align: left; }}
  #md-view th {{ background: #f0f4f8; font-weight: 600; }}
  #md-view tr:nth-child(even) {{ background: #fafbfc; }}
  #md-view code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-family: Consolas, Monaco, monospace; }}
  #md-view blockquote {{ background: #fff8e1; border-left: 4px solid #ffc107; padding: 10px 16px; margin: 14px 0; }}
  #md-view hr {{ border: none; border-top: 1px dashed #ccc; margin: 28px 0; }}
  .swagger-ui .topbar {{ display: none; }}
  .swagger-ui .info {{ margin: 20px 0; }}
</style>
</head>
<body>
<div class="topbar">
  <h1>📡 FusionCompute API 文档 — {variant_label}</h1>
  <div class="tabs" id="tabs"></div>
  <div class="meta">{total} paths · {size_mb:.1f} MB · 2026-06-06</div>
</div>
<div id="swagger-ui"></div>
<div id="md-view"></div>

{js_block}
<script>
  const OPENAPI_URLS = {swagger_urls_json};
  const MD_PAYLOADS = {md_payloads_json};
  const SPECS_META = {specs_meta_json};

  const tabsEl = document.getElementById('tabs');
  OPENAPI_URLS.forEach(spec => {{
    const btn = document.createElement('button');
    btn.className = 'tab';
    btn.dataset.id = 'oapi-' + spec.name;
    btn.textContent = '🔌 ' + spec.name;
    btn.onclick = () => switchOpenAPI(spec);
    tabsEl.appendChild(btn);
  }});
  Object.keys(MD_PAYLOADS).forEach(id => {{
    const btn = document.createElement('button');
    btn.className = 'tab';
    btn.dataset.id = 'md-' + id;
    btn.textContent = '📄 ' + id;
    btn.onclick = () => switchMD(id);
    tabsEl.appendChild(btn);
  }});

  let ui;
  function switchOpenAPI(spec) {{
    document.getElementById('md-view').classList.remove('active');
    document.getElementById('swagger-ui').classList.add('active');
    setActiveTab('oapi-' + spec.name);
    if (ui) {{
      ui.specActions.updateUrl(spec.url);
      ui.specActions.downloadUrl = spec.url;
    }} else {{
      ui = SwaggerUIBundle({{
        url: spec.url,
        dom_id: '#swagger-ui',
        deepLinking: true,
        docExpansion: 'list',
        filter: true,
        showExtensions: true,
        defaultModelsExpandDepth: -1,
        presets: [SwaggerUIBundle.presets.apis],
        layout: 'BaseLayout'
      }});
    }}
  }}

  function switchMD(id) {{
    document.getElementById('swagger-ui').classList.remove('active');
    const mdView = document.getElementById('md-view');
    mdView.classList.add('active');
    setActiveTab('md-' + id);
    if (!window.markdownit) return;
    if (!window._mdRenderer) {{
      window._mdRenderer = window.markdownit({{ html: true, linkify: true, typographer: true }});
    }}
    mdView.innerHTML = window._mdRenderer.render(MD_PAYLOADS[id]);
    mdView.scrollTop = 0;
  }}

  function setActiveTab(id) {{
    document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.id === id));
  }}

  window.onload = () => {{
    if (OPENAPI_URLS.length > 0) switchOpenAPI(OPENAPI_URLS[0]);
  }};
</script>
</body>
</html>
"""


def build_offline():
    print('=== Building OFFLINE (zero network deps) ===')
    swagger_css = (STATIC / 'swagger-ui.css').read_text(encoding='utf-8')
    swagger_js = (STATIC / 'swagger-ui-bundle.js').read_text(encoding='utf-8')
    markdown_js = (STATIC / 'markdown-it.min.js').read_text(encoding='utf-8')

    css_block = '<style>\n' + swagger_css + '\n</style>'
    js_block = (
        '<script>\n/* INLINE swagger-ui-bundle.js */\n' + swagger_js + '\n</script>\n'
        '<script>\n/* INLINE markdown-it.min.js */\n' + markdown_js + '\n</script>'
    )

    html = HTML_TEMPLATE.format(
        title='FusionCompute API 文档 (离线版)',
        variant_label='离线版',
        css_block=css_block,
        js_block=js_block,
        swagger_urls_json=json.dumps(build_swagger_urls(), ensure_ascii=False),
        md_payloads_json=json.dumps(build_md_payloads(), ensure_ascii=False),
        specs_meta_json=json.dumps(SPECS, ensure_ascii=False),
        total=total_paths(),
        size_mb=0,  # patched below
    )
    OUT_OFFLINE.write_text(html, encoding='utf-8')
    size_mb = OUT_OFFLINE.stat().st_size / 1024 / 1024
    # Patch size label
    text = OUT_OFFLINE.read_text(encoding='utf-8').replace('0.0 MB · 2026-06-06', f'{size_mb:.1f} MB · 2026-06-06')
    OUT_OFFLINE.write_text(text, encoding='utf-8')
    print(f'  -> {OUT_OFFLINE.name} ({size_mb:.2f} MB) [0 network deps]')
    return size_mb


def build_online():
    print('\n=== Building ONLINE (uses CDN) ===')
    css_block = '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css">'
    js_block = (
        '<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js" charset="UTF-8"></script>\n'
        '<script src="https://cdn.jsdelivr.net/npm/markdown-it@14.1.0/dist/markdown-it.min.js"></script>'
    )

    html = HTML_TEMPLATE.format(
        title='FusionCompute API 文档 (CDN版)',
        variant_label='CDN版',
        css_block=css_block,
        js_block=js_block,
        swagger_urls_json=json.dumps(build_swagger_urls(), ensure_ascii=False),
        md_payloads_json=json.dumps(build_md_payloads(), ensure_ascii=False),
        specs_meta_json=json.dumps(SPECS, ensure_ascii=False),
        total=total_paths(),
        size_mb=0,
    )
    OUT_ONLINE.write_text(html, encoding='utf-8')
    size_mb = OUT_ONLINE.stat().st_size / 1024 / 1024
    text = OUT_ONLINE.read_text(encoding='utf-8').replace('0.0 MB · 2026-06-06', f'{size_mb:.1f} MB · 2026-06-06')
    OUT_ONLINE.write_text(text, encoding='utf-8')
    print(f'  -> {OUT_ONLINE.name} ({size_mb:.2f} MB) [needs CDN]')
    return size_mb


if __name__ == '__main__':
    off = build_offline()
    on = build_online()
    print()
    print(f'=== DONE ===')
    print(f'  Offline: {OUT_OFFLINE} ({off:.2f} MB)')
    print(f'  Online:  {OUT_ONLINE} ({on:.2f} MB)')
