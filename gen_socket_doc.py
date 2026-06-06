"""Generate standalone documentation for BCManager <-> FusionCompute binary Socket protocol.

These 6 interfaces are NOT HTTP REST APIs (they use operation codes 1-5 + byte-level
binary payloads), so they cannot be expressed in OpenAPI/Swagger. We extract them
from the VRM docx and write a structured markdown document.
"""
import re
from pathlib import Path

EXTRACT = Path(r"C:\Users\steven\Desktop\fusion\_extracted")
OUT_DIR = Path(r"C:\Users\steven\Desktop\fusion\fusion-swagger")
OUT_FILE = OUT_DIR / "BCManager-Socket-Protocol.md"


def find_vrm_md():
    for p in EXTRACT.glob("*.md"):
        if p.stat().st_size == 3296580:  # VRM doc size
            return p
    raise FileNotFoundError("VRM markdown not found")


def parse_bcmanager_block(block_text: str, h3_title: str) -> dict:
    """Parse one BCManager socket interface block.

    Block structure uses TAB-separated section labels:
      ### 读远程代理文件
      接口说明\t读远程代理文件。
      操作码\t1 - 打开代理文件
      请求参数

      | 参数名 | 说明 | 字节数 | 是否必选 |
      |---|---|---|---|
      | name | desc | n | 是 |
      ...
      响应参数

      | 参数名 | 说明 | 字节数 | 是否必选 |
      |---|---|---|---|

    The first H3 "消息头处理" is a SHARED message header spec (no
    接口说明/操作码), not a per-interface block.
    """
    lines = block_text.split('\n')
    description = ''
    operation_code = None
    request_params = []
    response_params = []
    in_table = None  # 'request' | 'response' when currently parsing a table

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        s = line.strip()

        # Stop at next H3
        if s.startswith('### ') and i > 0:
            break

        # Tab-separated section: "section\tcontent"
        if '\t' in line:
            parts = line.split('\t', 1)
            section = parts[0].strip()
            content = parts[1].strip() if len(parts) > 1 else ''

            if section == '接口说明':
                description = content
                in_table = None
            elif section == '操作码':
                m = re.match(r'(\d+)\s*[-–—]\s*(.*)', content)
                if m:
                    operation_code = {'code': m.group(1), 'name': m.group(2).strip()}
                in_table = None
            elif section == '请求数据内容':
                in_table = 'request'
            elif section == '返回数据内容':
                in_table = 'response'
            else:
                # Generic tab-separated line (treat as continuation of description)
                if not description and content:
                    description = content
            i += 1
            continue

        # Section header alone (no tab content): "请求数据内容" on its own line
        if s == '请求数据内容' and '\t' not in line:
            in_table = 'request'
            i += 1
            continue
        if s == '返回数据内容' and '\t' not in line:
            in_table = 'response'
            i += 1
            continue

        # Table row
        if s.startswith('|') and in_table:
            if re.match(r'^\|[\s\-:|]+\|?$', s):
                i += 1
                continue
            cells = [c.strip() for c in s.split('|') if c.strip() != '']
            # Skip header row
            if cells and cells[0] in ('参数名', 'Name', '字段名', 'Parameter'):
                i += 1
                continue
            if cells and len(cells) >= 3:
                row = {
                    'name': cells[0],
                    'desc': cells[1] if len(cells) > 1 else '',
                    'bytes': cells[2] if len(cells) > 2 else '',
                    'required': cells[3] if len(cells) > 3 else '否',
                }
                if in_table == 'request':
                    request_params.append(row)
                else:
                    response_params.append(row)
        elif s.startswith('|') and not in_table:
            # Table without section header — attach to response (for 消息头处理)
            in_table = 'header'  # special: message header spec
            if re.match(r'^\|[\s\-:|]+\|?$', s):
                i += 1
                continue
            cells = [c.strip() for c in s.split('|') if c.strip() != '']
            if cells and cells[0] in ('参数名', 'Name'):
                i += 1
                continue
            if cells and len(cells) >= 3:
                request_params.append({
                    'name': cells[0],
                    'desc': cells[1] if len(cells) > 1 else '',
                    'bytes': cells[2] if len(cells) > 2 else '',
                    'required': cells[3] if len(cells) > 3 else '否',
                })
        i += 1

    return {
        'title': h3_title,
        'description': description,
        'operation': operation_code,
        'request_params': request_params,
        'response_params': response_params,
    }


def extract_bcmanager_interfaces():
    p = find_vrm_md()
    content = p.read_text(encoding='utf-8')
    lines = content.split('\n')

    # Find H2: "BCManager与FusionCompute Socket接口"
    h2_idx = None
    h2_title = ''
    for i, line in enumerate(lines):
        if re.match(r'^## BCManager.*Socket', line):
            h2_idx = i
            h2_title = line[3:].strip()
            break
    if h2_idx is None:
        raise RuntimeError("BCManager section not found in VRM doc")

    # Find all H3 under this H2 (until next H2)
    h3_blocks = []
    for i in range(h2_idx + 1, len(lines)):
        if re.match(r'^## ', lines[i]):
            break
        m = re.match(r'^### (.+)$', lines[i])
        if m:
            h3_blocks.append((i, m.group(1).strip()))

    # For each H3, get its block (until next H3 or H2)
    interfaces = []
    for j, (h3_line, h3_title) in enumerate(h3_blocks):
        # End: next H3 or H2
        end = h3_blocks[j+1][0] if j+1 < len(h3_blocks) else len(lines)
        # Also stop at next H2
        for k in range(h3_line+1, len(lines)):
            if re.match(r'^## ', lines[k]):
                end = k
                break
        block_text = '\n'.join(lines[h3_line:end])
        parsed = parse_bcmanager_block(block_text, h3_title)
        interfaces.append(parsed)

    return h2_title, interfaces


def render_markdown(h2_title: str, interfaces: list) -> str:
    out = []
    out.append("# BCManager ↔ FusionCompute 二进制 Socket 协议文档\n")
    out.append("> **重要**: 本文档描述的是 **二进制 socket 协议**（非 HTTP REST API），")
    out.append("> 因此**不纳入 OpenAPI/Swagger 文档**。\n")
    out.append("> 适用场景: BCManager 通过 TCP socket 与 FusionCompute VRM 通信，")
    out.append("> 用于远程代理文件读写、消息头处理等运维操作。\n")
    out.append("---\n")
    out.append(f"**来源**: 华为 FusionCompute 8.8.1 VRM 接口文档 → `{h2_title}` 章节\n")
    # Filter out the shared message header spec (first H3) from interface list
    real_ifaces = [iface for iface in interfaces if iface['operation'] is not None]
    header_iface = next((iface for iface in interfaces if iface['operation'] is None), None)
    out.append(f"**接口总数**: {len(real_ifaces)}（另有 1 个共享消息头规范）\n")
    out.append("\n---\n")
    out.append("## 目录\n")
    for i, iface in enumerate(real_ifaces, 1):
        out.append(f"{i}. [{iface['title']}](#op-{iface['operation']['code']}) - 操作码 `{iface['operation']['code']}`\n")
    if header_iface:
        out.append(f"{len(real_ifaces)+1}. [共享消息头规范](#message-header)\n")
    out.append("\n---\n")

    # Per-interface sections
    for i, iface in enumerate(real_ifaces, 1):
        out.append(f"\n## {i}. {iface['title']} {{#op-{iface['operation']['code']}}}\n")
        out.append(f"\n**操作码**: `{iface['operation']['code']}` ({iface['operation']['name']})\n")
        if iface['description']:
            out.append(f"\n**接口说明**: {iface['description']}\n")
        if iface['request_params']:
            out.append("\n### 请求参数\n")
            out.append("| 参数名 | 说明 | 字节数 | 是否必选 |\n")
            out.append("|---|---|---|---|\n")
            for p in iface['request_params']:
                out.append(f"| `{p['name']}` | {p['desc']} | {p['bytes']} | {p['required']} |\n")
        if iface['response_params']:
            out.append("\n### 响应参数\n")
            out.append("| 参数名 | 说明 | 字节数 | 是否必选 |\n")
            out.append("|---|---|---|---|\n")
            for p in iface['response_params']:
                out.append(f"| `{p['name']}` | {p['desc']} | {p['bytes']} | {p['required']} |\n")
        out.append("\n---\n")

    # Shared message header spec
    if header_iface:
        out.append(f"\n## {len(real_ifaces)+1}. 共享消息头规范 {{#message-header}}\n")
        out.append("\n**说明**: 所有接口共用的消息头格式（来自原文档「消息头处理」章节）。\n")
        if header_iface['request_params']:
            out.append("\n| 字段 | 说明 | 字节数 |\n")
            out.append("|---|---|---|\n")
            for p in header_iface['request_params']:
                out.append(f"| `{p['name']}` | {p['desc']} | {p['bytes']} |\n")
        out.append("\n---\n")

    # Error code table (synthesized from observed error codes)
    out.append("\n## 错误码总表\n")
    out.append("\n| 错误码 | 说明 | 出现于 |\n")
    out.append("|---|---|---|\n")
    seen_errors = set()
    error_summaries = {
        '0': '成功',
        '1': '参数错误',
        '2': '文件不存在',
        '3': 'Token 错误',
        '4': '文件打开标志错误',
        '5': '文件句柄错误',
    }
    for iface in real_ifaces:
        for p in iface['response_params']:
            m = re.search(r'Result.*?(\d+)\s*[—–-]\s*([^,，）)]+)', p['desc'])
            if m:
                code = m.group(1)
                if code not in seen_errors:
                    seen_errors.add(code)
                    out.append(f"| {code} | {m.group(2).strip()} | {iface['title']} |\n")
    # Always include common ones
    for code, desc in error_summaries.items():
        if code not in seen_errors:
            out.append(f"| {code} | {desc} | (常见) |\n")

    out.append(f"\n*本文档由 Claude 从原始 docx 抽取生成 (2026-06-06)*\n")
    return ''.join(out)


if __name__ == '__main__':
    print("=== Extracting BCManager Socket interfaces ===")
    h2_title, interfaces = extract_bcmanager_interfaces()
    print(f"  Section: {h2_title}")
    print(f"  Interfaces found: {len(interfaces)}")
    for iface in interfaces:
        op = iface['operation']['code'] if iface['operation'] else '?'
        n_req = len(iface['request_params'])
        n_resp = len(iface['response_params'])
        print(f"    - [{op}] {iface['title']}: request={n_req} response={n_resp}")

    md = render_markdown(h2_title, interfaces)
    OUT_FILE.write_text(md, encoding='utf-8')
    print(f"\n  -> {OUT_FILE} ({len(md)} chars)")
    print("\n=== DONE ===")
