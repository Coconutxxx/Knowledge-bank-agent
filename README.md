# 本地知识库问答 Agent

这是一个面向初学者的、可在 VS Code 中运行的知识库问答项目。它保留了参考文章中的核心思想：

- 大脑：OpenAI 兼容格式的大模型；
- 工具：`knowledge_search` 本地知识库检索工具；
- 记忆：最近 8 轮对话；
- 循环：Agent 决定检索 → 观察检索结果 → 继续检索或输出回答。

同时增加了完整的 RAG 流程：

```text
PDF / Word / Excel / SQL / TXT
              ↓
        文档读取与切分
              ↓
      本地嵌入模型生成向量
              ↓
        Chroma 持久化存储
              ↓
用户提问 → Agent 调用检索工具 → 证据片段 → 带来源的回答
```

## 一、你会得到什么

- Streamlit 图形界面：上传资料、导入、聊天、查看引用；
- 命令行入口：便于观察程序运行逻辑；
- 本地 Chroma 向量数据库；
- 支持 `.pdf`、`.docx`、`.xlsx`、`.csv`、`.sql`、`.txt`、`.md` 等；
- 支持 OpenAI、DeepSeek、智谱等 OpenAI 兼容接口，也可连接 Ollama；
- 中文本地嵌入模型默认使用 `BAAI/bge-small-zh-v1.5`。

## 二、Windows + VS Code 环境配置

### 第 1 步：安装软件

安装以下软件：

1. Python 3.11（建议使用 3.11，不建议一开始使用刚发布的新版本）；
2. VS Code；
3. VS Code 中的 Microsoft Python 扩展。

安装 Python 时务必勾选 **Add Python to PATH**。

打开 PowerShell，检查：

```powershell
python --version
pip --version
```

如果 `python` 找不到，可以尝试：

```powershell
py --version
```

### 第 2 步：在 VS Code 打开项目

1. 解压项目压缩包；
2. 启动 VS Code；
3. 选择“文件 → 打开文件夹”；
4. 选择解压后的 `knowledge-base-agent` 文件夹；
5. 选择“终端 → 新建终端”。

后续命令都在 VS Code 下方的 PowerShell 终端中执行。

### 第 3 步：创建虚拟环境

```powershell
python -m venv .venv
```

如果你的电脑只能使用 `py`：

```powershell
py -3.11 -m venv .venv
```

激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 提示禁止运行脚本，先执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

激活成功后，终端行首会出现 `(.venv)`。

### 第 4 步：让 VS Code 使用虚拟环境

按 `Ctrl + Shift + P`，输入并选择：

```text
Python: Select Interpreter
```

选择路径中带有 `.venv` 的 Python。

### 第 5 步：安装依赖

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果下载较慢，可以临时使用镜像：

```powershell
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

注意：PyTorch 和向量模型相关依赖体积较大，首次安装需要一些时间。这个项目做文本问答时使用 CPU 即可，不要求显卡，也不需要单独安装 CUDA。

### 第 6 步：配置大模型

在 VS Code 文件列表中复制 `.env.example`，把副本改名为 `.env`。

使用 OpenAI 时：

```env
OPENAI_API_KEY=你的API_Key
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o-mini
```

使用 DeepSeek 时：

```env
OPENAI_API_KEY=你的DeepSeek_API_Key
OPENAI_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-chat
```

不要把真实 API Key 发给别人，也不要上传 `.env` 文件；本项目已在 `.gitignore` 中忽略它。

### 第 7 步：启动图形界面

```powershell
streamlit run app.py
```

浏览器通常会自动打开：

```text
http://localhost:8501
```

如果没有自动打开，把这个地址复制到浏览器。

### 第 8 步：导入知识并提问

1. 在左侧“上传资料”中选择文件；
2. 点击“导入所选文件”；
3. 第一次导入时会自动下载中文向量模型，请耐心等待；
4. 导入完成后，在底部输入问题；
5. 展开“查看检索来源”核对 Agent 依据了哪些原文片段。

项目自带 `data/knowledge/示例知识.txt`。可以先在终端导入它：

```powershell
python cli.py ingest data/knowledge
```

然后启动命令行问答：

```powershell
python cli.py chat
```

## 三、代码结构

```text
knowledge-base-agent/
├── app.py                         # Streamlit 图形界面
├── cli.py                         # 命令行入口
├── requirements.txt
├── .env.example
├── data/
│   ├── knowledge/                 # 可直接放待导入文件
│   └── uploads/                   # 网页上传文件的本地副本
├── storage/                       # Chroma 向量数据库
├── src/
│   ├── config.py
│   ├── core/
│   │   ├── agent.py               # ReAct 主循环
│   │   └── llm_client.py
│   ├── memory/
│   │   └── conversation.py
│   ├── rag/
│   │   ├── document_loader.py     # 文件解析
│   │   ├── splitter.py            # 文本切分
│   │   ├── vector_store.py        # 向量化、存储、检索
│   │   └── indexer.py
│   └── tools/
│       └── knowledge_search.py    # Agent 检索工具
└── tests/
    └── test_splitter.py
```

## 四、它与参考文章的关系

参考文章构建的是通用任务 Agent，工具包括计算器、文件读写和网页请求。本项目把同一个架构改造成知识库 Agent：

| 参考文章 | 本项目 |
|---|---|
| LLMClient | 保留，并支持 OpenAI 兼容接口 |
| Calculator / File / Web 工具 | 改为 KnowledgeSearchTool |
| ConversationMemory | 保留，仅记录最终对话 |
| 文本格式 ReAct | 改为 JSON 格式 ReAct，解析更稳定 |
| 命令行入口 | 保留，同时增加 Streamlit 页面 |
| 无知识库 | 增加文档解析、切分、嵌入、Chroma 检索 |

## 五、建议先理解的运行流程

假设提问：“Hive 中为什么不能直接 update？”

1. `KnowledgeAgent.run()` 把问题交给大模型；
2. 大模型输出调用 `knowledge_search` 的 JSON；
3. `VectorStore.search()` 把问题转换为向量并检索相似片段；
4. 工具把 `[来源1] ...` 等证据返回给 Agent；
5. Agent 根据证据生成最终回答；
6. 页面展示回答，同时在折叠区展示原始来源片段。

这比“每个问题固定检索一次”的普通 RAG 多了一个 Agent 决策层：Agent 可以修改关键词并再次检索。

## 六、常见问题

### 1. `AuthenticationError`

检查 `.env` 的 API Key、`OPENAI_BASE_URL` 和模型名称是否属于同一家服务商。修改 `.env` 后重启 Streamlit。

### 2. `ModuleNotFoundError`

通常是 VS Code 选错了解释器。确认终端行首有 `(.venv)`，再执行：

```powershell
pip install -r requirements.txt
```

### 3. 首次启动很慢

第一次创建 `VectorStore` 时会下载嵌入模型。完成后模型会缓存在本机，后续启动会快很多。

### 4. PDF 导入后没有内容

扫描版 PDF 只有图片，没有文本层，`pypdf` 无法直接识别。需要先做 OCR，或后续接入 PaddleOCR。

### 5. 回答和原文对不上

先展开“查看检索来源”：

- 如果来源不相关，调整 `CHUNK_SIZE`、`CHUNK_OVERLAP`、`TOP_K`；
- 如果来源正确但回答错误，优化 `SYSTEM_PROMPT` 或换更合适的聊天模型；
- 如果完全没有来源，确认文件确实已经导入。

### 6. 重复导入会不会重复？

每个文本块使用“来源 + 位置 + 序号 + 内容”生成固定哈希 ID，完全相同的内容会执行 upsert，不会无限重复。

### 7. 怎么运行测试？

```powershell
pytest -q
```

## 七、下一步扩展顺序

建议按以下顺序逐步扩展，不要一开始就把系统做得过重：

1. 增加文档删除和按文件筛选；
2. 增加混合检索与重排序模型；
3. 为扫描 PDF 增加 OCR；
4. 增加回答评价集（问题、标准答案、来源）；
5. 增加 FastAPI 后端和权限控制；
6. 最后再考虑多 Agent、联网检索或生产部署。

