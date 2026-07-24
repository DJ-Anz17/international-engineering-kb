# GitHub 同类项目比较（调研日期：2026-07-24）

## 结论

个人起步不直接部署大型平台。当前实现吸收了成熟项目的关键思路，但把运行单元缩小为“文件目录 + SQLite + 可选 Ollama + MCP”。当资料量、扫描件或多人权限需求增长时，再按下表升级。

| 项目 | 值得借鉴 | 主要代价/边界 | 本项目的取舍 |
|---|---|---|---|
| [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | 桌面端易用；多格式、来源引用、Ollama/多向量库、MCP；MIT | 行业元数据、合同/报价工作流仍需自己组织；有可关闭的遥测 | 借鉴开箱即用与本地模型接口；本实现默认零遥测并内置行业分类 |
| [RAGFlow](https://github.com/infiniflow/ragflow) | 复杂文档理解、可视化切块、可追溯引用、多路召回与重排 | 官方要求至少 4 核/16GB/50GB/Docker；2026-07 官方预构建镜像仍不支持 ARM64 | 不作为当前 Apple Silicon 个人机的起步底座；扫描件规模上来后优先评估 |
| [Kotaemon](https://github.com/Cinnamon/kotaemon) | 混合检索、重排、PDF 高亮引用、复杂推理、Ollama；Python 可扩展 | 完整依赖和解析链路较重；专业元数据仍需定制 | 直接借鉴“全文+向量融合”和低相关度应提示的原则 |
| [MaxKB](https://github.com/1Panel-dev/MaxKB) | 中文界面、RAG、工作流、MCP、Ollama；企业应用成熟 | Django/Vue/PostgreSQL+pgvector 整套运行；GPLv3 | 若未来要多人审批和可视化工作流，可迁移；个人阶段保持简单 |
| [Open WebUI](https://github.com/open-webui/open-webui) | Ollama 体验好；多解析器；BM25+向量与重排；离线模式 | 更偏通用 AI 门户；当前许可证含品牌保留要求 | 可作为未来统一聊天前端，本项目继续做行业资料和 MCP 层 |
| [OpenDocuments](https://github.com/joungminsung/OpenDocuments) | 本地文件/外部连接器、引用、Web/CLI/MCP、Ollama、混合检索；MIT | 截至调研仅约百星，成熟度和长期维护仍需观察 | MCP 暴露知识库的思路最接近本实现；当前不直接引入其依赖栈 |
| [Dify](https://github.com/langgenius/dify) | 强大的智能体/Chatflow 编排、自托管 | 对单人资料管理偏重；知识库与复杂解析往往还需外部组件 | 未来需要自动生成周报、审批流或多系统连接时再接入 |

## 推荐升级路径

1. **当前阶段（个人、数千到数万页）**：使用本项目。原文件和元数据保持供应商中立，任何时候可重建索引。
2. **扫描书籍和复杂表格增多**：给本项目增加 Docling/MinerU OCR，或把 RAGFlow/Kotaemon 作为解析层。
3. **统一 AI 门户**：使用本项目 MCP 接入 Codex、Claude/Cursor 等客户端，或让 Open WebUI/AnythingLLM 做聊天前端。
4. **多人、权限、审计与流程**：评估 MaxKB/Dify；原有目录和元数据继续作为权威资料源。
5. **服务器级海量资料**：迁移向量层到 Qdrant/pgvector，并增加文档级 ACL、备份、监控和检索评测集。

## 为什么没有直接 fork 某个项目

- 当前机器没有 Docker/Ollama，且是 ARM64；大型平台的初次部署和后续升级会掩盖真正重要的资料治理工作。
- 国际工程问答的价值不只在向量数据库，而在版本、国别、项目、合同范本、有效日期和保密级别等元数据。
- 本实现核心只依赖 Python 标准库，数据库是单一 SQLite 文件；未来更换 UI、模型或向量库不会锁住原始资料。
