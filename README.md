# 本地国际工程个人知识库

这是一套已经可运行的、本地优先的国际工程资料库。它不是通用聊天壳，而是把“资料管理—检索—引用—专业分析—AI 调用”连成一条可审计的工作流。

## 已实现

- 国际工程专用九大资料域：投标报价、技术方案、工效资源、风险/HSE、合同索赔、国别市场、项目复盘、标准规范、模板清单；
- PDF、EPUB、MOBI/AZW/AZW3、DOCX、XLSX、PPTX/PPTM、RTF、Markdown、TXT、CSV、HTML、JSON 等格式；
- 中文字符 n-gram + 英文关键词 + 国际工程同义词的全文检索；
- Ollama + BGE-M3 在本机完成向量检索，采用全文/向量融合排序；
- 可选择 Ollama、Gemini、Qwen、Kimi、OpenAI 或 GLM 生成回答，云端 API Key 保存在 macOS 钥匙串；
- 所有结果保留原文件、页码/工作表/幻灯片定位和原文片段；
- 八种分析模式：依据问答、报价复核、技术审查、工效测算、风险登记册、合同审查、索赔通知、国别分析；
- 本地网页、命令行和 MCP 三种入口；
- 默认只监听 `127.0.0.1`，没有遥测，不向云端发送资料；
- 增量索引、文件删除同步、元数据筛选、上传到“待分类”。
- 上传后会显示向量化覆盖率；Ollama 临时不可用时仍保留全文索引，恢复后再次点击“增量更新索引”会自动补齐缺失向量。
- 左侧“资料目录”可直接打开已索引的原文件，并显示每份资料的向量覆盖情况。
- 融合 `learn-from-materials` 思路：材料安全扫描、单文档学习范围、快速了解、分主题系统学习、学习自检、浏览器本地笔记和 `.learnkb.zip` 可追溯离线学习包。

## 5 分钟开始

## 已部署的 macOS 本地服务

本机安装后的运行副本位于：

```text
~/Library/Application Support/InternationalEngineeringKB
```

- 登录后自动启动 Ollama 和知识库；
- 桌面的“国际工程知识库”快捷方式可直接打开；
- 本项目目录中的 `本地资料库` 链接指向实际资料目录；
- 双击 `run.command` 可检查服务并打开网页；
- 双击 `stop-local.command` 可停止两个用户级服务。
- 源代码更新后，双击 `update-local.command` 可保留资料和索引并更新已安装的运行副本。
- 如果更新后网页仍显示“资料目录暂不可用”，先双击 `stop-local.command`，再双击 `run.command`；`run.command` 会检测旧后台并重新拉起服务。

本地地址始终为 [http://127.0.0.1:8765](http://127.0.0.1:8765)，默认不对局域网开放。

### 1. 先用纯本地检索（不需要安装模型）

在终端进入本目录，执行：

```bash
python3 -m ieg_kb init
python3 -m ieg_kb ingest
python3 -m ieg_kb serve
```

浏览器打开 [http://127.0.0.1:8765](http://127.0.0.1:8765)。macOS 也可以直接双击 `run.command`。

纯检索模式可处理 Office、文本和表格；PDF 需要下一步安装 `pypdf`。

### 2. 安装 PDF 解析

双击 `setup.command`，或执行：

```bash
./setup.command
```

它只在本目录创建 `.venv`，并安装 `pypdf`。不会安装云服务。

### 3. 可选：启用完全本地 AI

双击 `install-local-ai.command`。脚本会先要求输入 `YES`，然后通过 Homebrew 安装 Ollama，下载：

- `qwen3:8b`：本地中文/英文分析；
- `bge-m3`：多语向量检索。

模型占用数 GB；不需要 AI 生成回答时可跳过。模型安装后，重新运行 `./reindex.command` 即可建立向量索引。

### 4. 选择 AI 提供商和模型

系统支持以下回答服务：

- `Ollama`：完全本地，可使用本机已经安装的 Qwen 等模型；
- `Gemini`：Google Gemini API；
- `Qwen`：阿里云百炼兼容接口；
- `Kimi`：月之暗面兼容接口；
- `OpenAI`：OpenAI API；
- `GLM`：智谱开放平台兼容接口。
- `DeepSeek`：DeepSeek 官方 OpenAI 兼容接口，提供 V4 Flash 和 V4 Pro。

双击 `configure-ai.command`，选择服务商并粘贴相应 API Key。每个 Key 都单独进入 macOS 钥匙串，不会写入 `kb_config.json`、日志或 Git。然后在网页左侧选择“AI 提供商”和“回答模型”，点击“应用模型选择”。

OpenAI 模型列表包含 `ChatGPT 5.6 Luna · Max`：实际 API 模型为 `gpt-5.6-luna`，并自动使用 `reasoning_effort: max`。界面采用易读名称，但不会伪造 `gpt-5.6-luna-max` 模型标识。

无论选择哪种回答模型，`bge-m3` 都在本机完成资料向量检索。选择云端服务时，只有用户问题和命中的少量证据片段会发送给相应服务商；原始文件、SQLite 索引和完整资料不会上传。发送合同、投标或项目资料前，请确认其保密要求允许发送给所选服务商。

## 放入自己的资料

推荐把原始文件复制到 [library](library) 对应目录；拿不准的先放 `00_待分类`。随后：

```bash
python3 -m ieg_kb ingest
```

也可以在网页左侧上传，系统会先放入“待分类”并立即索引。

## 材料学习功能

网页左侧“指定学习资料”用于把检索严格限制在一份文件。选中资料后可使用三种学习任务：

- **材料快速了解**：提炼核心框架、必要术语、工程启示和材料边界；
- **材料系统学习（分主题）**：围绕指定章节或主题展开定义、机制、适用条件、易混点和行动规则；
- **材料学习自检**：只依据命中的原文证据生成记忆、解释、应用和迁移题。

长书的“系统学习”应按章节或主题分批执行。系统会明确当前命中范围，不会把若干检索片段冒充整本书的完整覆盖。

每条检索证据可以收藏到“我的本地笔记”。笔记只保存在当前浏览器的 `localStorage` 中，可以导出 JSON，不会自动同步到云端。

点击“导出所选资料学习包”会生成并下载 `<文档ID>.learnkb.zip`，其中包括：

- 可全文搜索和记录本地笔记的单文件 `learning.html`；
- 带来源 ID、定位和内容 SHA-256 的 `full_text.md`；
- `source_map.json`、`source_manifest.json`、`metadata.json`；
- `material-security-report.json` 和 `INDEX.md`。

命令行也可以导出：

```bash
python3 -m ieg_kb learning-pack <文档ID>
```

DOCX、PPTX/PPTM、XLSX 和 EPUB 会先检查路径穿越、加密条目、异常展开体积及压缩比。材料中的提示词、角色覆盖、外传要求和命令只会被标记为待复核数据，不会执行。MOBI/AZW/AZW3 需要本机已有 Calibre 的 `ebook-convert`；缺失时知识库会给出明确解析警告。

### 元数据

在原文件旁增加同名 `.meta.json`。例如：

```text
FIDIC_Red_Book_2017.pdf
FIDIC_Red_Book_2017.pdf.meta.json
```

元数据示例：

```json
{
  "title": "FIDIC Conditions of Contract for Construction",
  "category": "合同与索赔",
  "subcategory": "FIDIC与范本",
  "country": "",
  "project": "",
  "contract_form": "FIDIC 2017 Red Book",
  "discipline": "合同",
  "document_type": "合同范本",
  "language": "en",
  "version": "2nd Ed. 2017",
  "effective_date": "2017-01-01",
  "confidentiality": "内部",
  "source_org": "FIDIC",
  "tags": ["变更", "索赔", "工期", "付款"]
}
```

元数据会进入筛选条件和引用信息。实际项目建议至少维护：`title`、`country`、`project`、`contract_form`、`version`、`effective_date`、`confidentiality`。

## 常用命令

```bash
# 环境检查
python3 -m ieg_kb doctor

# 增量索引
python3 -m ieg_kb ingest

# 强制重建并生成向量
python3 -m ieg_kb ingest --force --embeddings on

# 直接检索
python3 -m ieg_kb search "变更通知期限" --category "合同与索赔"

# 使用配置的 AI 服务分析
python3 -m ieg_kb ask "复核本项目的索赔通知程序" --mode claim_notice

# 统计
python3 -m ieg_kb status
```

## MCP：让其他 AI 调用

MCP 服务提供四个只读工具：

- `kb_search`：检索并返回可引用原文；
- `kb_get_document`：按文档 ID 分页读取；
- `kb_status`：查看资料库状态；
- `kb_answer`：由配置的 AI 服务生成专业分析。

启动命令是：

```bash
./mcp.command
```

将 [mcp-config.example.json](mcp-config.example.json) 中的服务器项加入支持 MCP 的 AI 客户端。移动本目录后，需要更新其中的绝对路径。建议 AI 的工作方式是先调用 `kb_search`，在回答中引用返回的路径和定位；涉及合同、法律、税务与 HSE 的结论必须人工复核。

## 数据与备份

- 原始资料：`library/`，这是最重要的备份对象；
- 元数据：与原文件同目录的 `*.meta.json`；
- 配置：`kb_config.json`；
- 可重建索引：`data/kb.sqlite3`；
- 专业任务模板：`templates/`。

备份至少包含 `library/`、`kb_config.json` 和 `templates/`。SQLite 索引可以用 `python3 -m ieg_kb ingest --force` 重建。

## 重要边界

- 扫描 PDF：`pypdf` 只能提取已有文字层；平均文字过少时会给出 OCR 警告。大量扫描书籍建议升级到 Docling、MinerU、Kotaemon 或 RAGFlow 的解析链路。
- 表格：复杂合并单元格、公式结果、图表和嵌入对象可能无法由轻量解析器完整恢复，关键报价表需人工核对原文件。
- 时效：法律、税务、汇率、市场价和国家政策有有效期，必须维护 `effective_date` 并检查最新来源。
- 版权：只导入你有权持有和使用的资料；不要对外传播受版权或保密义务限制的书籍、投标文件与合同。
- 专业责任：系统提供证据检索与审查辅助，不替代律师、税务顾问、造价师、工程师或 HSE 负责人的签署意见。

## 设计资料

- [GitHub 项目比较](docs/GITHUB_PROJECT_COMPARISON.md)
- [系统架构与检索逻辑](docs/ARCHITECTURE.md)
- [日常治理与建设路线](docs/OPERATIONS.md)
- [learn-from-materials 功能融合说明](docs/LEARN_FROM_MATERIALS_INTEGRATION.md)
- [第三方开源说明](THIRD_PARTY_NOTICES.md)
