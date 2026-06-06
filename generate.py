"""
FusionCompute → OpenAPI 3.0 YAML converter
============================================
Parses 8 markdown files (extracted from .docx) and produces 5 OpenAPI 3.0 YAML:
  - vrm.yaml       (FusionCompute 8.8.1 VRM 主接口, ~500 endpoints)
  - container.yaml (FusionCompute 8.8.1 容器接口, ~230 endpoints)
  - as.yaml        (弹性伸缩 8.8.0 + 8.9.0 merged)
  - image.yaml     (镜像服务 8.8.0 + 8.9.0 merged)
  - kms.yaml       (KMS 加密机)

Output dir: C:/Users/steven/Desktop/fusion/fusion-swagger/
"""
import re
import json
import yaml
from pathlib import Path
from collections import OrderedDict
from typing import Any

ROOT = Path(r"C:\Users\steven\Desktop\fusion")
EXTRACT = ROOT / "_extracted"
OUT = ROOT / "fusion-swagger"
OUT.mkdir(parents=True, exist_ok=True)

# ==================== MD TABLE PARSER ====================
def parse_md_table(lines):
    """Parse markdown pipe table from list of lines.
    Returns list of rows, each row is list of cell strings.
    Skips separator rows (|---|---|)."""
    rows = []
    for line in lines:
        s = line.strip()
        if not s.startswith('|'):
            continue
        if re.match(r'^\|[\s\-:|]+\|?$', s):
            continue
        # split on |, drop empty first/last
        parts = s.split('|')
        if parts and parts[0] == '':
            parts = parts[1:]
        if parts and parts[-1] == '':
            parts = parts[:-1]
        cells = [p.strip() for p in parts]
        rows.append(cells)
    return rows


def dedupe_repeated_cells(row):
    """Docx tables often have merged cells flattened — same value across columns.
    Return a deduped row, preserving order."""
    if not row:
        return row
    out = [row[0]]
    for cell in row[1:]:
        if cell != out[-1]:
            out.append(cell)
    return out


# ==================== TYPE INFERENCE ====================
def infer_type(value: str) -> str:
    """Heuristic type inference from docstring descriptions.
    Examples: 'string', 'integer', 'boolean', 'array', 'object'."""
    v = (value or '').strip().lower()
    if not v:
        return 'string'
    if v in ('string', 'str'):
        return 'string'
    if v in ('integer', 'int', 'long', 'number'):
        return 'integer'
    if v in ('boolean', 'bool'):
        return 'boolean'
    if v.startswith('array') or 'array of' in v or 'list' in v:
        return 'array'
    if v.startswith('object') or 'object<' in v:
        return 'object'
    if v.startswith('map<') or v.startswith('dict'):
        return 'object'
    return 'string'


# ==================== PATH NORMALIZATION ====================
def normalize_path(raw: str) -> str:
    """Extract path from request line.

    Examples:
      'Put <site_uri>/<site_id> HTTP/1.1 ...'       -> '/{site_id}'
      'Get https://<ip>:<port>/<site_uri>/<site_id>' -> '/{site_id}'
      'DELETE /service/sites/{site_id} HTTP/1.1'     -> '/service/sites/{site_id}'
    """
    if not raw:
        return '/'
    # Cut at " HTTP/" to get the request line only
    http_idx = re.search(r'\s+HTTP/\d', raw)
    body = raw[:http_idx.start()].strip() if http_idx else raw.strip()
    # Strip method keyword
    body = re.sub(r'^\s*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+', '', body, flags=re.I)
    # If it's a full URL, take the path portion (after scheme://host:port)
    url_m = re.search(r'https?://[^\s/]+(/[^\s]*)', body)
    if url_m:
        body = url_m.group(1)
    # If body still starts with host-style content (no /), strip leading <...>:
    # e.g. '<site_uri>/<site_id>' -> take after first '/'
    if '://' in body:
        # last resort: take everything from first '/'
        idx = body.find('/', body.find('://') + 3)
        if idx >= 0:
            body = body[idx:]
    # Ensure leading /
    if not body.startswith('/'):
        body = '/' + body
    # Normalize <param> to {param} (allow optional whitespace inside)
    body = re.sub(r'<\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*>', r'{\1}', body)
    # Strip query string for path normalization
    body = body.split('?')[0]
    # Collapse multiple slashes
    body = re.sub(r'/+', '/', body)
    return body


def extract_method_path(request_text: str):
    """From request row text, return (method, path) tuple."""
    if not request_text:
        return ('GET', '/')
    method_match = re.match(r'\s*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\b', request_text, re.I)
    method = method_match.group(1).upper() if method_match else 'POST'
    path = normalize_path(request_text)
    return (method, path)


# ==================== ENDPOINT BLOCK PARSER ====================
def split_doc_into_blocks(content: str):
    """Yield (h2_title, h3_title, block_text) for each H3 under H2."""
    lines = content.split('\n')
    current_h2 = None
    current_h2_line = -1
    current_h3_line = -1
    blocks = []

    # Find all H2 and H3 positions
    h2_positions = []  # (line_idx, title)
    h3_positions = []  # (line_idx, title)
    for i, line in enumerate(lines):
        if re.match(r'^## ', line):
            h2_positions.append((i, line[3:].strip()))
        elif re.match(r'^### ', line):
            h3_positions.append((i, line[4:].strip()))

    if not h2_positions:
        # No H2 — treat whole doc as one tag
        for j, (h3_line, h3_title) in enumerate(h3_positions):
            start = h3_line
            end = h3_positions[j+1][0] if j+1 < len(h3_positions) else len(lines)
            blocks.append(('默认', h3_title, '\n'.join(lines[start:end])))
        return blocks

    # For each H3, find its parent H2
    for j, (h3_line, h3_title) in enumerate(h3_positions):
        parent = None
        for h2_line, h2_title in h2_positions:
            if h2_line < h3_line:
                parent = (h2_line, h2_title)
            else:
                break
        # Determine block end
        end = h3_positions[j+1][0] if j+1 < len(h3_positions) else len(lines)
        # Also stop at next H2
        for h2_line, _ in h2_positions:
            if h2_line > h3_line and h2_line < end:
                end = h2_line
                break
        block_text = '\n'.join(lines[h3_line:end])
        blocks.append((parent[1] if parent else '默认', h3_title, block_text))
    return blocks


def parse_endpoint_block(h2_tag: str, h3_title: str, block_text: str) -> dict:
    """Parse single endpoint H3 block into structured data.

    Section markers observed in FusionCompute docs (first column of 2D table):
      接口功能  = one-line summary
      接口描述  = parameters table (col2=name, col3=type, col4=description)
      请求 / 请求方式 / 请求参数 / 请求消息头 = HTTP method/path or header info
      响应 / 响应方式 / 响应字段 / 响应消息头 = response status / fields
      错误码 = error code table (col1=HTTP, col2=code, col3=description)
      说明 / 备注 = free-text description

    IMPORTANT: Due to docx table cell flattening, the first column of EVERY
    row in a section is the same section label (e.g. row 1-15 all have first=
    "接口描述"). We track the previous first-column to distinguish the actual
    section header row from data rows.
    """
    lines = block_text.split('\n')
    rows = parse_md_table(lines)

    summary = ''
    description = ''
    parameters = []
    request_method = 'POST'
    request_path = '/'
    error_codes = []
    request_headers = []
    response_headers = []

    section = None
    prev_first = None  # Track the previous first-column to detect real section transitions

    KNOWN_SECTIONS = {
        '接口功能': 'summary',
        '接口描述': 'parameters',
        '请求': 'request',
        '请求方式': 'request',
        '请求消息': 'request',
        '请求样例': 'request',
        '请求示例': 'request',
        '请求参数': 'request_params',
        '请求消息头': 'request_headers',
        '请求头': 'request_headers',
        '响应': 'response',
        '响应方式': 'response',
        '响应消息': 'response',
        '响应样例': 'response',
        '响应示例': 'response',
        '响应字段': 'response_fields',
        '响应消息头': 'response_headers',
        '响应头': 'response_headers',
        '返回': 'response',
        '错误码': 'errors',
        '错误': 'errors',
        '错误信息': 'errors',
        '说明': 'description',
        '备注': 'description',
        '事件类型': 'event',
        '事件响应消息': 'event_response',
        '异步任务': 'async_task',
        '异步任务响应': 'async_task',
        '异步任务响应消息': 'async_task',
        '异步任务响应说明': 'async_task',
        '同步任务响应': 'sync_task',
    }
    HEADER_LIKE = ('Name', 'Attribute', 'Type', 'Description', 'HTTP状态码', 'Error Code', '')

    for row in rows:
        if not row:
            continue
        first = row[0].strip() if row else ''
        if not first:
            continue

        # ---- Section transition (only when first-column actually changes) ----
        if first in KNOWN_SECTIONS and first != prev_first:
            section = KNOWN_SECTIONS[first]
            prev_first = first
            # NOTE: do NOT continue here — the data for request/response sections
            # often lives in THIS very row (row[1] is the URL/method/headers text).
            # Fall through to data-row processing below.
            # For summary/description sections, if row[1] has content, capture it.
            if section == 'summary' and len(row) > 1 and row[1]:
                summary = row[1]
                continue
            if section == 'description' and len(row) > 1 and row[1]:
                description = row[1]
                continue
            # For other sections (request/response/etc), fall through to handle this row's data
        # If first == prev_first (a repeated section label in a data row),
        # fall through to data-row processing below.

        # ---- Skip header-marker rows in non-parameter sections ----
        if first in HEADER_LIKE and section != 'parameters':
            continue

        # ---- Data row processing ----
        if section == 'parameters':
            # row: [section, name, type, description]  (4 cells)
            if len(row) >= 4:
                name, ptype, desc = row[1], row[2], row[3]
            elif len(row) == 3:
                name, ptype, desc = row[0], row[1], row[2]
            elif len(row) == 2:
                name, ptype, desc = row[0], row[1], ''
            else:
                continue
            if name in HEADER_LIKE:
                continue
            req = '必选' in desc or '必填' in desc or 'required' in desc.lower()
            t = infer_type(ptype)
            desc_clean = re.sub(r'（.*?KVM未支持.*?）', '', desc)
            desc_clean = re.sub(r'\(KVM.*?\)', '', desc_clean)
            desc_clean = desc_clean.strip()
            parameters.append({
                'name': name,
                'type': t,
                'description': desc_clean,
                'required': req,
                'in': 'body',
            })
        elif section == 'errors':
            if len(row) >= 4:
                ec_http, ec_code, ec_desc = row[1], row[2], row[3]
            elif len(row) == 3:
                ec_http, ec_code, ec_desc = row[0], row[1], row[2]
            else:
                continue
            if ec_http in HEADER_LIKE:
                continue
            error_codes.append({
                'http': ec_http,
                'code': ec_code,
                'description': ec_desc
            })
        elif section == 'request':
            # Some endpoints have request method/path in row 2+ (continued)
            if len(row) > 1 and request_path == '/' and row[1] and row[1] != first:
                m, p = extract_method_path(row[1])
                request_method, request_path = m, p
        elif section == 'description':
            if not description and len(row) > 1 and row[1]:
                description = row[1]
        elif section == 'request_headers':
            if len(row) >= 2 and row[1] and row[1] not in HEADER_LIKE:
                request_headers.append({'name': row[1], 'desc': row[2] if len(row) > 2 else ''})
        elif section == 'response_headers':
            if len(row) >= 2 and row[1] and row[1] not in HEADER_LIKE:
                response_headers.append({'name': row[1], 'desc': row[2] if len(row) > 2 else ''})

    return {
        'tag': h2_tag,
        'summary': h3_title,
        'description': description or summary,
        'method': request_method,
        'path': request_path,
        'parameters': parameters,
        'error_codes': error_codes,
        'request_headers': request_headers,
        'response_headers': response_headers,
    }


# ==================== OPERATION ID ====================
def to_operation_id(method: str, path: str, tag: str) -> str:
    """Generate camelCase operationId from method+path."""
    parts = re.findall(r'\{?([a-zA-Z_][a-zA-Z0-9_]*)\}?', path)
    parts = [p for p in parts if p not in ('service', 'api', 'v1', 'v2')]
    base = ''.join(p.capitalize() for p in parts) or 'root'
    return f"{method.lower()}{base}"


# ==================== OPENAPI YAML RENDERER ====================
def render_openapi_yaml(title: str, version: str, description: str, endpoints: list) -> str:
    """Build OpenAPI 3.0 YAML string."""
    spec = OrderedDict()
    spec['openapi'] = '3.0.3'
    spec['info'] = OrderedDict([
        ('title', title),
        ('version', version),
        ('description', description),
    ])
    spec['servers'] = [{
        'url': 'https://{hostname}:{port}',
        'variables': {
            'hostname': {'default': 'vrm.example.com', 'description': 'FusionCompute VRM 主机 IP'},
            'port': {'default': '8443', 'description': 'HTTPS 端口'},
        }
    }]
    # Group endpoints by tag → tags
    tags_seen = []
    paths = OrderedDict()
    for ep in endpoints:
        tag = ep['tag']
        if tag not in tags_seen:
            tags_seen.append(tag)
        path = ep['path']
        method = ep['method'].lower()
        if path not in paths:
            paths[path] = {}
        op = OrderedDict()
        op['tags'] = [tag]
        op['summary'] = ep['summary']
        if ep['description'] and ep['description'] != ep['summary']:
            op['description'] = ep['description']
        op['operationId'] = to_operation_id(ep['method'], ep['path'], tag)
        # Security
        op['security'] = [{'X-Auth-Token': []}]
        # Path-level params (extract from {name} in path)
        path_params = []
        for m in re.finditer(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', path):
            path_params.append(OrderedDict([
                ('name', m.group(1)),
                ('in', 'path'),
                ('required', True),
                ('schema', {'type': 'string'}),
                ('description', f'路径参数 {m.group(1)}'),
            ]))
        # Body parameters
        body_params = [p for p in ep['parameters'] if p['in'] == 'body']
        query_params = [p for p in ep['parameters'] if p['in'] == 'query']
        all_params = path_params + [
            OrderedDict([
                ('name', p['name']),
                ('in', p['in']),
                ('required', p['required']),
                ('schema', {'type': p['type']}),
                ('description', p['description']),
            ]) for p in query_params
        ]
        if all_params:
            op['parameters'] = all_params
        if body_params:
            props = OrderedDict()
            for p in body_params:
                props[p['name']] = OrderedDict([
                    ('type', p['type']),
                    ('description', p['description']),
                ])
                if p['required']:
                    props[p['name']] = OrderedDict([
                        ('type', p['type']),
                        ('description', p['description']),
                    ])
            body_schema = OrderedDict([
                ('type', 'object'),
                ('properties', props),
            ])
            op['requestBody'] = OrderedDict([
                ('required', True),
                ('content', {
                    'application/json': {
                        'schema': body_schema
                    }
                })
            ])
        # Responses
        responses = OrderedDict()
        responses[ep.get('status', '200')] = OrderedDict([
            ('description', '操作成功'),
        ])
        if ep['error_codes']:
            # group error codes by HTTP status
            by_status = {}
            for ec in ep['error_codes']:
                by_status.setdefault(ec['http'], []).append(ec)
            for status, codes in by_status.items():
                resp = OrderedDict()
                resp['description'] = f'HTTP {status} 错误'
                resp['content'] = {
                    'application/json': {
                        'schema': {
                            'type': 'object',
                            'properties': {
                                'errorCode': {'type': 'string', 'description': '错误码', 'example': codes[0]['code'] if codes else ''},
                                'message': {'type': 'string', 'description': '错误描述'}
                            }
                        },
                        'examples': {
                            f'err_{c["code"]}': {
                                'value': {'errorCode': c['code'], 'message': c['description']}
                            } for c in codes[:5]
                        }
                    }
                }
                responses[status] = resp
        op['responses'] = responses
        paths[path][method] = op

    spec['tags'] = [{'name': t, 'description': f'{t} 相关接口'} for t in tags_seen]
    spec['paths'] = paths

    # Components
    spec['components'] = OrderedDict([
        ('securitySchemes', {
            'X-Auth-Token': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'X-Auth-Token',
                'description': '通过 /service/session 接口获取的 token'
            }
        })
    ])

    # Convert OrderedDicts to plain dicts (Python 3.7+ dicts preserve insertion order)
    spec_plain = _to_plain(spec)

    # Dump as YAML with proper ordering and width
    return yaml.dump(spec_plain, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)


def _to_plain(obj):
    """Recursively convert OrderedDict/OrderedDict-like to plain dict, preserve order."""
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(x) for x in obj]
    return obj


def parse_endpoint_block_v2(h2_tag: str, h3_title: str, block_text: str) -> dict:
    """V2 parser for Container/AS/Image docs (plain-text format).

    Structure (Container):
      ### <endpoint name>
      功能简介
      <text>
      调用方法
      GET|POST|PUT|DELETE
      URI
      /path/to/endpoint
      请求query参数列表 / 请求body参数列表
      | 参数 | 类型 | 是否必选 | 描述 |
      | name | String | 否 | desc |
      请求示例
      ...
      响应参数
      响应状态码为200: successful operation
      响应Body参数列表
      | 参数 | 类型 | 是否必选 | 描述 |
      ...

    Structure (AS/Image — uses H2 as endpoint):
      ## <endpoint name>
      功能简介
      ...
    """
    lines = block_text.split('\n')
    summary = ''
    description = ''
    method = 'GET'
    path = '/'
    parameters = []
    error_codes = []
    status_code = '200'

    rows = parse_md_table(lines)
    # Build a list of (line_idx, content) for non-table scanning
    i = 0
    cur_section = None
    while i < len(lines):
        line = lines[i].strip()
        # 1. 功能简介
        if line == '功能简介':
            cur_section = 'summary'
            i += 1
            # collect text until next known heading or table
            txt = []
            while i < len(lines):
                l = lines[i].strip()
                if l in ('调用方法', 'URI', '请求query参数列表', '请求body参数列表',
                         '请求示例', '请求头', '响应参数', '响应Body参数列表',
                         '响应示例', '响应头', '状态码', '错误码', '接口认证'):
                    break
                if l.startswith('|'):
                    break
                if l:
                    txt.append(l)
                i += 1
            summary = ' '.join(txt).strip()
            continue
        # 2. 调用方法
        if line == '调用方法':
            i += 1
            # next non-empty line is method
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                m = re.match(r'(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)', lines[i].strip(), re.I)
                if m:
                    method = m.group(1).upper()
            i += 1
            continue
        # 3. URI
        if line == 'URI':
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                p = lines[i].strip()
                # Normalize template variables
                p = re.sub(r'\{\{([^}]+)\}\}', r'{\1}', p)  # {{var}} -> {var}
                p = re.sub(r'<([a-zA-Z_][a-zA-Z0-9_]*)>', r'{\1}', p)
                if not p.startswith('/'):
                    p = '/' + p
                # collapse double slashes
                p = re.sub(r'/+', '/', p)
                path = p
            i += 1
            continue
        # 4. 请求query参数列表 / 请求body参数列表
        if line in ('请求query参数列表', '请求body参数列表', '请求Body参数列表',
                    '请求Path参数列表', '请求Header参数列表', '请求参数列表'):
            section_name = line
            i += 1
            # skip separator
            while i < len(lines) and (not lines[i].strip() or re.match(r'^\|[\s\-:|]+\|?$', lines[i].strip())):
                i += 1
            # collect table rows
            in_query = 'query' in line
            while i < len(lines):
                l = lines[i].strip()
                if not l.startswith('|'):
                    break
                if re.match(r'^\|[\s\-:|]+\|?$', l):
                    i += 1
                    continue
                cells = [c.strip() for c in l.split('|') if c.strip() != '']
                if cells and cells[0] not in ('参数', 'Name', '字段名', 'Parameter'):
                    # cells: [name, type, required, desc]
                    name = cells[0]
                    ptype = cells[1] if len(cells) > 1 else 'string'
                    desc = cells[-1] if len(cells) > 2 else ''
                    if name and name not in ('参数', '字段名'):
                        t = infer_type(ptype)
                        req = any(k in (cells[2] if len(cells) > 2 else '') for k in ('必选', '必填', '是', 'Y', 'yes'))
                        # Clean desc
                        desc = re.sub(r'（.*?）', '', desc).strip()
                        parameters.append({
                            'name': name,
                            'type': t,
                            'description': desc,
                            'required': req,
                            'in': 'query' if in_query else 'body',
                        })
                i += 1
            continue
        # 5. 响应Body参数列表
        if line in ('响应Body参数列表', '响应参数列表'):
            i += 1
            while i < len(lines) and (not lines[i].strip() or re.match(r'^\|[\s\-:|]+\|?$', lines[i].strip())):
                i += 1
            while i < len(lines):
                l = lines[i].strip()
                if not l.startswith('|'):
                    break
                if re.match(r'^\|[\s\-:|]+\|?$', l):
                    i += 1
                    continue
                # response fields - we don't add to parameters; skip
                i += 1
            continue
        # 6. 响应参数 / 状态码
        if line in ('响应参数', '状态码', '错误码'):
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                m = re.search(r'(\d{3})', lines[i])
                if m:
                    status_code = m.group(1)
                    error_codes.append({'http': status_code, 'code': 'OK', 'description': lines[i].strip()[:80]})
            i += 1
            continue
        i += 1

    return {
        'tag': h2_tag,
        'summary': h3_title,
        'description': description or summary,
        'method': method,
        'path': path,
        'parameters': parameters,
        'error_codes': error_codes,
        'request_headers': [],
        'response_headers': [],
    }


def split_doc_into_blocks_v2(content: str, endpoint_level: int = 3):
    """For AS/Image where endpoint is at H2. For Container, endpoint is at H3."""
    lines = content.split('\n')
    h1_positions = []
    h2_positions = []
    h3_positions = []
    for i, line in enumerate(lines):
        if re.match(r'^# ', line):
            h1_positions.append((i, line[2:].strip()))
        elif re.match(r'^## ', line):
            h2_positions.append((i, line[3:].strip()))
        elif re.match(r'^### ', line):
            h3_positions.append((i, line[4:].strip()))

    blocks = []
    if endpoint_level == 2:
        # Use H2 as endpoint (AS/Image style)
        positions = h2_positions
    else:
        positions = h3_positions

    for j, (line, title) in enumerate(positions):
        # Determine parent tag (use nearest H1 or H2 above)
        parent = None
        if endpoint_level == 2:
            # H2 endpoint, parent is H1
            for h1_line, h1_title in h1_positions:
                if h1_line < line:
                    parent = (h1_line, h1_title)
                else:
                    break
        else:
            # H3 endpoint, parent is H2
            for h2_line, h2_title in h2_positions:
                if h2_line < line:
                    parent = (h2_line, h2_title)
                else:
                    break
        # Block end: next endpoint-level or parent-level
        end = positions[j+1][0] if j+1 < len(positions) else len(lines)
        if endpoint_level == 2:
            for h1_line, _ in h1_positions:
                if h1_line > line and h1_line < end:
                    end = h1_line
                    break
        else:
            for h2_line, _ in h2_positions:
                if h2_line > line and h2_line < end:
                    end = h2_line
                    break
        block_text = '\n'.join(lines[line:end])
        blocks.append((parent[1] if parent else '默认', title, block_text))
    return blocks


# ==================== MAIN PIPELINE ====================
def find_md(size: int) -> Path:
    for p in EXTRACT.glob('*.md'):
        if p.stat().st_size == size:
            return p
    raise FileNotFoundError(f"No md with size {size}")


def process_vrm():
    print("\n=== Processing VRM (8.8.1) ===")
    p = find_md(3296580)
    content = p.read_text(encoding='utf-8')
    blocks = split_doc_into_blocks(content)
    # Filter: keep H3 that look like endpoints (verb-starting) AND have request method in block
    endpoints = []
    for h2, h3, block in blocks:
        ep = parse_endpoint_block(h2, h3, block)
        # Only keep if path was extracted (i.e., request_message section was found)
        if ep['path'] != '/':
            endpoints.append(ep)
    print(f"  Total blocks: {len(blocks)}, Kept as endpoints: {len(endpoints)}")
    yaml_text = render_openapi_yaml(
        title='FusionCompute 8.8.1 VRM REST API',
        version='8.8.1',
        description='华为 FusionCompute 8.8.1 VRM (Virtual Resource Management) REST API。\n\n'
                    '包含计算虚拟化、存储虚拟化、网络虚拟化、OM API、性能监控、数据保护、CDP、事件上报等模块。\n\n'
                    '认证: 通过 POST /service/session 获取 X-Auth-Token，后续请求需在 Header 携带。',
        endpoints=endpoints
    )
    out = OUT / 'vrm.yaml'
    out.write_text(yaml_text, encoding='utf-8')
    print(f"  -> {out} ({len(yaml_text)} chars, {len(endpoints)} endpoints)")


def process_container():
    print("\n=== Processing Container (8.8.1) — v2 plain-text parser ===")
    p = find_md(555798)
    content = p.read_text(encoding='utf-8')
    blocks = split_doc_into_blocks_v2(content, endpoint_level=3)  # Container uses H3
    endpoints = []
    for h2, h3, block in blocks:
        ep = parse_endpoint_block_v2(h2, h3, block)
        if ep['path'] != '/':
            endpoints.append(ep)
    print(f"  Total blocks: {len(blocks)}, Kept: {len(endpoints)}")
    yaml_text = render_openapi_yaml(
        title='FusionCompute 8.8.1 Container API',
        version='8.8.1',
        description='华为 FusionCompute 8.8.1 容器服务 REST API (krm 1.0).',
        endpoints=endpoints
    )
    out = OUT / 'container.yaml'
    out.write_text(yaml_text, encoding='utf-8')
    print(f"  -> {out} ({len(yaml_text)} chars, {len(endpoints)} endpoints)")


def process_kms():
    print("\n=== Processing KMS (8.8.1) ===")
    p = find_md(81876)
    content = p.read_text(encoding='utf-8')
    blocks = split_doc_into_blocks(content)
    endpoints = []
    for h2, h3, block in blocks:
        ep = parse_endpoint_block(h2, h3, block)
        if ep['path'] != '/':
            endpoints.append(ep)
    print(f"  Total blocks: {len(blocks)}, Kept: {len(endpoints)}")
    yaml_text = render_openapi_yaml(
        title='FusionCompute 8.8.1 KMS 加密机 API',
        version='8.8.1',
        description='华为 FusionCompute 8.8.1 KMS 加密机 REST API。',
        endpoints=endpoints
    )
    out = OUT / 'kms.yaml'
    out.write_text(yaml_text, encoding='utf-8')
    print(f"  -> {out} ({len(yaml_text)} chars, {len(endpoints)} endpoints)")


def process_as_and_image():
    """AS and image have 8.8.0 + 8.9.0 versions.
    - AS: identical between versions (verified 2026-06-06), keep merge.
    - Image: has 1 new endpoint + 15 param changes. Split paths by version prefix.
    """
    pairs = [
        ('as', '弹性伸缩', 113184, 113094,
         'FusionCompute Auto Scaling Service REST API (8.8.0 + 8.9.0 — verified identical, merged)',
         'merge'),
        ('image', '镜像服务', 58905, 65520,
         'FusionCompute Image Service (Glance) REST API — 8.8.0 and 8.9.0 split as /v8.8.0/* and /v9.0.0/* to preserve per-version params (8.9.0 added 1 endpoint, 15 endpoints have different query params)',
         'split'),
    ]
    for tag, label, sz_old, sz_new, desc, mode in pairs:
        print(f"\n=== Processing {label} — mode={mode} ===")
        all_endpoints = []
        for sz, ver in [(sz_old, '8.8.0'), (sz_new, '8.9.0')]:
            p = find_md(sz)
            content = p.read_text(encoding='utf-8')
            blocks = split_doc_into_blocks_v2(content, endpoint_level=2)
            for h2, h3, block in blocks:
                ep = parse_endpoint_block_v2(h2, h3, block)
                if ep['path'] != '/':
                    if mode == 'split':
                        # Add version prefix to path: /v8.8.0/rest/...  /v8.9.0/rest/...
                        version_tag = 'v8.8.0' if ver == '8.8.0' else 'v8.9.0'
                        if ep['path'].startswith('/'):
                            ep['path'] = '/' + version_tag + ep['path']
                        else:
                            ep['path'] = '/' + version_tag + '/' + ep['path']
                        # Re-apply path-level template normalization after prefix
                    ep['description'] = f"[{ver}] " + (ep['description'] or ep['summary'])
                    all_endpoints.append(ep)
        yaml_text = render_openapi_yaml(
            title=f'FusionCompute {label} API',
            version='8.8.0+8.9.0' if mode == 'merge' else '8.8.0 / 8.9.0 (split)',
            description=desc,
            endpoints=all_endpoints
        )
        out = OUT / f'{tag}.yaml'
        out.write_text(yaml_text, encoding='utf-8')
        print(f"  -> {out} ({len(yaml_text)} chars, {len(all_endpoints)} endpoints)")


if __name__ == '__main__':
    process_vrm()
    process_container()
    process_kms()
    process_as_and_image()
    print("\n=== ALL DONE ===")
    for f in sorted(OUT.glob('*.yaml')):
        print(f"  {f.name}: {f.stat().st_size} bytes")
