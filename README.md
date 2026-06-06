# FusionCompute API 文档

华为 **FusionCompute 8.8.1** 全量 REST API + 二进制 Socket 协议文档（自动从原始 docx 抽取生成）。

## 📦 交付物

| 文件 | 用途 |
|------|------|
| **`FusionCompute-API-OFFLINE.html`** (4.7 MB) | **完全离线单文件** — 双击直接打开，**零网络依赖** |
| `FusionCompute-API-ONLINE.html` (3.1 MB) | CDN 版单文件，体积小但需联网 |
| `index.html` | 导航入口（多文件版） |
| `*.yaml` (5 个) | 原始 OpenAPI 3.0 规范 |
| `BCManager-Socket-Protocol.md` | BCManager 二进制 Socket 协议（不在 OpenAPI） |
| `vrm.html / container.html / as.html / image.html / kms.html / bcmanager.html` | 6 个独立 Swagger UI 文档 |
| `*.py` (5 个) | docx → markdown → OpenAPI → HTML 全套生成器 |

## 📊 文档规模

| 服务 | paths | 说明 |
|------|-------|------|
| 🖥️ VRM 主接口 | 454 | 计算/存储/网络/OM/监控/数据保护/CDP/事件 |
| 📦 容器服务 (krm) | 185 | 容器 + 集群管理 |
| 📈 弹性伸缩 AS | 20 | 8.8.0 / 8.9.0 合并（验证完全相同） |
| 🖼️ 镜像服务 Image | 35 | 8.8.0 / 8.9.0 拆 path 保留差异 |
| 🔐 KMS 加密机 | 22 | 密钥管理 |
| 🔌 BCManager Socket | 5 ops | **二进制协议**，独立 markdown 文档 |
| **总计** | **721 paths** | |

## 🚀 快速使用

### 1. 直接看文档（最快）

双击 `FusionCompute-API-OFFLINE.html` 即可使用。**所有 6 个 spec 内嵌在单文件中**，顶部 tab 切换：

- 🖥️ VRM (454) / 📦 Container (185) / 📈 AS (20) / 🖼️ Image (35) / 🔐 KMS (22) / 🔌 BCManager Socket (5)
- 716 个 REST endpoint + 5 个二进制 socket 操作码
- 全部支持过滤搜索、Try it out、Schema 浏览

### 2. 集成到代码 / Postman / CI

直接使用 `*.yaml` 文件（OpenAPI 3.0 规范）：

```bash
# Postman
postman import --file vrm.yaml

# 验证
swagger-cli validate vrm.yaml

# 代码生成
openapi-generator-cli generate -i vrm.yaml -g python -o ./client
```

## 🔄 如何重新生成

需要 Python 3.10+，装 `python-docx openpyxl pyyaml`：

```bash
pip install python-docx openpyxl pyyaml

# 1. 从 docx 抽取 markdown（_extracted/ 目录）
python _extracted/extract.py
# 注：原始 docx 在 C:\Users\steven\Desktop\fusion\

# 2. 解析生成 OpenAPI YAML
python generate.py

# 3. 生成多文件 HTML
python build_html.py

# 4. 生成单文件 HTML（同时输出 OFFLINE + ONLINE）
python build_single_html.py
```

## 📝 已知限制

1. **VRM 有 22 个 H3 章节**未提取（5 类原因）：
   - 3 个 Rest 接口格式说明（章节文档）
   - 8 个元数据定义（字段表，非 endpoint）
   - 6 个 BCManager Socket 接口（二进制协议，独立处理）
   - 4 个事件类型 schema（非 endpoint）
   - 1 个「站点连通性检查」原文档只写了一个「无」字
2. **AS 8.8.0 / 8.9.0 完全相同**，已合并
3. **Image 8.8.0 / 8.9.0 有差异**：用 `/v8.8.0/*` 和 `/v8.9.0/*` 拆 path 保留两版
4. **Schema 未递归嵌套**（如 VM 配置是平铺）
5. **docx 编码是 cp936 抽取为 UTF-8**，部分文档结构变体可能识别失败

## 🛠️ 技术栈

- **抽取**：`python-docx` (docx → markdown)
- **解析**：自研 Python 脚本，2 种 parser（VRM/KMS 用 2D 表格，Container/AS/Image 用纯文本）
- **OpenAPI 渲染**：`pyyaml`
- **Swagger UI**：[swagger-ui-dist 5.17.14](https://github.com/swagger-api/swagger-ui)
- **Markdown 渲染**：[markdown-it 14.1.0](https://github.com/markdown-it/markdown-it)

## 📅 版本

- 生成时间：2026-06-06
- 数据来源：华为 FusionCompute 8.8.1 (VRM / Container / KMS) + 8.8.0 & 8.9.0 (AS / Image) 接口参考文档
- 生成工具：Claude (Sonnet 4.6) 自动化抽取
