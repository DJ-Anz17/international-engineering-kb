# 系统架构与检索逻辑

```text
原始资料 library/
  ├─ 文件路径给出默认分类
  └─ *.meta.json 补充国别/项目/版本/合同范本/标签
           │
           ▼
解析器 PDF / DOCX / XLSX / PPTX / Text / HTML
           │
           ▼
按页/工作表/幻灯片切分，约 1,200 字，180 字重叠
           │
     ┌─────┴─────────┐
     ▼               ▼
SQLite FTS5       Ollama BGE-M3（可选）
中文 n-gram/BM25  多语语义向量
     └─────┬─────────┘
           ▼
        RRF 融合排序
           │
     ┌─────┼──────────┐
     ▼     ▼          ▼
   网页   CLI       MCP 工具
           │
           ▼
Ollama Qwen（可选）+ 专业分析模板 + [S1] 来源引用
```

## 权威数据边界

- `library/` 是权威原始资料；
- `*.meta.json` 是权威元数据；
- `data/kb.sqlite3` 是派生索引，可删除重建；
- AI 回答也是派生内容，不应替代原文件。

## 中文检索

SQLite 默认分词对中文长句不理想。索引会把中文序列生成 2/3 字符 n-gram，把英文保留为单词/缩写；查询时还会扩展国际工程中英同义词，例如：

```text
工程量清单 → BOQ / bill of quantities
变更 → variation / change order / VO
工期延长 → EOT / extension of time
履约保函 → performance security / performance bond
```

全文结果与 BGE-M3 语义结果采用 Reciprocal Rank Fusion 融合。没有 Ollama 时，系统自动退化为全文检索，不影响基本使用。

## 引用

每个片段保存：文档 ID、相对路径、页码/工作表/幻灯片、标题、分类和正文。模型上下文使用 `[S1]` 编号，回答后再次解析引用号，网页将编号对应到原文件。

## 安全

- HTTP 默认绑定 `127.0.0.1`；
- `send_documents_to_cloud=false` 时，代码拒绝把检索片段发送到非本机 Ollama 地址；
- 文件下载接口限制在 `library/` 内，阻断路径穿越；
- 上传文件名去除路径和控制字符，且只接受配置白名单格式；
- MCP 不提供删除、移动或重建索引工具，降低 AI 误操作风险。
