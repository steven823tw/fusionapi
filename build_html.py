"""Generate self-contained HTML Swagger UI docs from 5 YAML files.

Each HTML embeds Swagger UI via CDN and inlines its YAML as a data URL,
so the file works offline-friendly from file:// (CDN needs network only).
"""
import base64
from pathlib import Path

ROOT = Path(r"C:\Users\steven\Desktop\fusion\fusion-swagger")
SPECS = [
    ('vrm',       'VRM 主接口',       '华为 FusionCompute 8.8.1 VRM REST API — 计算/存储/网络/OM/监控/数据保护/CDP/事件', 'vrm.yaml'),
    ('container', '容器服务',         '华为 FusionCompute 8.8.1 容器服务 (krm) REST API',                            'container.yaml'),
    ('as',        '弹性伸缩 AS',      '华为 FusionCompute 弹性伸缩服务 REST API (8.8.0 + 8.9.0 — 完全相同，已合并)',  'as.yaml'),
    ('image',     '镜像服务 Image',   '华为 FusionCompute 镜像服务 (Glance) REST API — 8.8.0 / 8.9.0 拆 path 保留差异', 'image.yaml'),
    ('kms',       'KMS 加密机',       '华为 FusionCompute 8.8.1 KMS 加密机 REST API',                               'kms.yaml'),
    ('bcmanager', 'BCManager Socket', 'BCManager ↔ FusionCompute **二进制 socket 协议**（不进 Swagger，独立文档）', 'BCManager-Socket-Protocol.md'),
]

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{title} — Swagger UI</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css">
<style>
  body {{ margin: 0; padding: 0; }}
  .topbar {{ display: none; }}
  .info {{ margin: 20px 0; }}
  #swagger-ui .scheme-container {{ background: #fafafa; padding: 10px 20px; }}
</style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js" charset="UTF-8"></script>
<script>
window.onload = () => {{
  window.ui = SwaggerUIBundle({{
    url: "{data_url}",
    dom_id: "#swagger-ui",
    deepLinking: true,
    docExpansion: "list",
    filter: true,
    showExtensions: true,
    showCommonExtensions: true,
    defaultModelsExpandDepth: -1,
    presets: [
      SwaggerUIBundle.presets.apis
    ],
    layout: "BaseLayout"
  }});
}};
</script>
</body>
</html>
"""

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>FusionCompute API 文档索引</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    margin: 0; padding: 0; min-height: 100vh;
  }}
  .container {{
    max-width: 1100px; margin: 0 auto; padding: 40px 20px;
  }}
  h1 {{
    color: #fff; font-size: 2.4em; margin: 0 0 10px;
    text-shadow: 0 2px 10px rgba(0,0,0,0.2);
  }}
  .subtitle {{ color: rgba(255,255,255,0.85); margin-bottom: 40px; font-size: 1.05em; }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px;
  }}
  .card {{
    background: #fff; border-radius: 12px; padding: 24px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.15);
    transition: transform 0.2s, box-shadow 0.2s;
    text-decoration: none; color: #333; display: block;
  }}
  .card:hover {{
    transform: translateY(-4px);
    box-shadow: 0 12px 32px rgba(0,0,0,0.25);
  }}
  .card-icon {{
    width: 48px; height: 48px; border-radius: 10px;
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    display: flex; align-items: center; justify-content: center;
    font-size: 24px; color: #fff; margin-bottom: 16px;
  }}
  .card-title {{ font-size: 1.3em; font-weight: 600; margin-bottom: 8px; }}
  .card-desc {{ color: #666; font-size: 0.92em; line-height: 1.5; margin-bottom: 16px; min-height: 50px; }}
  .card-meta {{
    display: flex; justify-content: space-between; align-items: center;
    padding-top: 12px; border-top: 1px solid #eee;
    font-size: 0.85em; color: #888;
  }}
  .badge {{
    display: inline-block; padding: 2px 10px; border-radius: 12px;
    background: #e8f4fd; color: #1976d2; font-weight: 500;
  }}
  .footer {{
    text-align: center; color: rgba(255,255,255,0.7);
    margin-top: 40px; font-size: 0.9em;
  }}
</style>
</head>
<body>
<div class="container">
  <h1>📡 FusionCompute API 文档</h1>
  <p class="subtitle">华为 FusionCompute 8.8.1 全量 OpenAPI 3.0 文档 · 点击下方卡片进入交互式 Swagger UI</p>
  <div class="grid">
{cards}
  </div>
  <p class="footer">本页面与各 HTML 文档由 Claude 自动从原始 docx 抽取生成 · {total_endpoints} 个 API endpoints</p>
</div>
</body>
</html>
"""


def make_data_url(yaml_text: str) -> str:
    """Encode YAML as data URL for Swagger UI to load inline."""
    b64 = base64.b64encode(yaml_text.encode('utf-8')).decode('ascii')
    return f"data:application/yaml;base64,{b64}"


def make_html(spec_id, title, desc, yaml_path):
    yaml_text = yaml_path.read_text(encoding='utf-8')
    data_url = make_data_url(yaml_text)
    html = HTML_TEMPLATE.format(title=title, data_url=data_url)
    out = ROOT / f"{spec_id}.html"
    out.write_text(html, encoding='utf-8')
    return out, len(yaml_text)


def make_bcmanager_html():
    """BCManager is markdown-only (binary protocol, not OpenAPI)."""
    md_path = ROOT / 'BCManager-Socket-Protocol.md'
    if not md_path.exists():
        return None
    md_text = md_path.read_text(encoding='utf-8')
    # Use markdown-it via CDN
    html = BCMANAGER_TEMPLATE.format(md=md_text)
    out = ROOT / 'bcmanager.html'
    out.write_text(html, encoding='utf-8')
    return out


BCMANAGER_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>BCManager Socket 协议 — 文档</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    max-width: 1100px; margin: 30px auto; padding: 0 20px; color: #333; line-height: 1.7;
  }}
  h1 {{ border-bottom: 3px solid #2a5298; padding-bottom: 10px; color: #1e3c72; }}
  h2 {{ border-bottom: 1px solid #ddd; padding-bottom: 6px; margin-top: 40px; color: #2a5298; }}
  h3 {{ color: #444; margin-top: 24px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #d0d0d0; padding: 8px 12px; text-align: left; }}
  th {{ background: #f0f4f8; font-weight: 600; }}
  tr:nth-child(even) {{ background: #fafbfc; }}
  code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-family: "Consolas", "Monaco", monospace; }}
  blockquote {{
    background: #fff8e1; border-left: 4px solid #ffc107;
    padding: 10px 16px; margin: 16px 0;
  }}
  hr {{ border: none; border-top: 1px dashed #ccc; margin: 30px 0; }}
  a {{ color: #1976d2; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .nav {{ background: #f5f5f5; padding: 10px 16px; border-radius: 6px; margin-bottom: 20px; }}
  .nav a {{ margin-right: 14px; }}
</style>
</head>
<body>
<div class="nav">
  <a href="index.html">← 返回首页</a>
  <a href="#">BCManager Socket 协议</a>
</div>
<pre id="raw" style="display:none;">{md}</pre>
<div id="rendered"></div>
<script src="https://cdn.jsdelivr.net/npm/markdown-it@14.1.0/dist/markdown-it.min.js"></script>
<script>
  const md = window.markdownit({{ html: true, linkify: true, typographer: true }});
  document.getElementById('rendered').innerHTML = md.render(document.getElementById('raw').textContent);
</script>
</body>
</html>
"""


def make_index():
    import yaml
    cards = []
    total_eps = 0
    icons = ['🖥️', '📦', '📈', '🖼️', '🔐', '🔌']
    for i, (sid, title, desc, yfile) in enumerate(SPECS):
        ypath = ROOT / yfile
        try:
            if yfile.endswith('.md'):
                # BCManager markdown: count operations from text
                text = ypath.read_text(encoding='utf-8')
                import re
                n_ops = len(re.findall(r'操作码:', text))
                n_tags = 0
                total_eps += n_ops
                badge = f"{n_ops} 个操作"
                meta = "二进制协议"
            else:
                with open(ypath, encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                n_paths = len(data.get('paths', {}))
                n_tags = len(data.get('tags', []))
                total_eps += n_paths
                badge = f"{n_paths} endpoints"
                meta = f"{n_tags} 个分类"
        except Exception as e:
            badge = "加载失败"
            meta = str(e)[:30]
        cards.append(
            f'    <a class="card" href="{sid}.html">\n'
            f'      <div class="card-icon">{icons[i]}</div>\n'
            f'      <div class="card-title">{title}</div>\n'
            f'      <div class="card-desc">{desc}</div>\n'
            f'      <div class="card-meta"><span class="badge">{badge}</span><span>{meta}</span></div>\n'
            f'    </a>'
        )
    html = INDEX_TEMPLATE.format(cards='\n'.join(cards), total_endpoints=total_eps)
    out = ROOT / 'index.html'
    out.write_text(html, encoding='utf-8')
    return out, total_eps


if __name__ == '__main__':
    print("=== Generating Swagger UI HTML files ===")
    for sid, title, desc, yfile in SPECS:
        ypath = ROOT / yfile
        if not ypath.exists():
            print(f"  [SKIP] {yfile} not found")
            continue
        if yfile.endswith('.md'):
            out = make_bcmanager_html()
            if out:
                print(f"  [OK] {out.name} ({out.stat().st_size/1024:.0f} KB) <- {yfile}")
        else:
            out, size = make_html(sid, title, desc, ypath)
            print(f"  [OK] {out.name} ({out.stat().st_size/1024:.0f} KB) <- {yfile}")
    print()
    out, total = make_index()
    print(f"  [OK] {out.name} ({out.stat().st_size/1024:.0f} KB)")
    print()
    print(f"=== DONE: {total} total endpoints across {len(SPECS)} specs ===")
    print(f"Open: {ROOT / 'index.html'}")
