# AI SRE 故障诊断 Agent

> 软件产品综合实践开发 — 实验二：Bring Your Own Agent (BYOA)

基于 **MCP** 的多场景 AI SRE 故障诊断 Agent，支持 **IndexError** 与 **KeyError** 两类 incident，含 BM25 RAG、Reflexion 与阶段编排。

## 场景

| 场景 | 命令 | 故障类型 |
|------|------|----------|
| `indexerror` | `python main.py` | 循环 off-by-one → IndexError |
| `keyerror` | `python main.py --scenario keyerror` | 字典 key 类型不匹配 → KeyError |

```bash
python main.py --list-scenarios   # 列出所有场景
```

## 架构

```
main.py --scenario <name>
    ↓
Agent Orchestrator  (ASSESS → INVESTIGATE → REMEDIATE → VERIFY)
    ↓ Function Calling
LLM ↔ MCP Server (6 tools + list_scenario_info)
    ├── read_logs / git_recent_changes / query_runbook (BM25 RAG)
    ├── read_source / apply_patch / run_tests
    └── 按 SRE_SCENARIO 环境变量切换 fixtures 路径
```

## 快速开始

```bash
pip install -r requirements.txt
copy .env.example .env

# 离线验证
python scripts/test_mcp_tools.py indexerror
python scripts/test_mcp_tools.py keyerror
pytest tests/ -v

# 可选：初始化 git 历史（git_recent_changes 用真实 log）
python scripts/setup_git_history.py

# 运行 Agent
python main.py                      # IndexError 场景
python main.py --scenario keyerror  # KeyError 场景
```

## 目录结构

```
software_lab/
├── main.py                         # CLI 入口 (--scenario)
├── agent/
│   ├── scenario.py                 # 场景注册表
│   ├── orchestrator.py             # CoT + Reflexion + 阶段编排
│   ├── mcp_client.py / llm_client.py
├── mcp_server/
│   ├── sre_tools.py                # MCP Server（7 工具）
│   ├── rag.py                      # BM25 分块 RAG
│   └── git_helper.py               # 真实 git log + fixture 回退
├── fixtures/
│   ├── logs/ + repo/               # indexerror 场景
│   ├── scenarios/keyerror/         # keyerror 场景
│   └── runbooks/                   # 共享 RAG 知识库（含误导 hotfix）
├── prompts/scenarios/              # 各场景告警文本
├── tests/                          # RAG + 场景单元测试
└── runs/                           # trace_<scenario>_<time>.json
```

## 课件技术覆盖

| 技术 | 实现 |
|------|------|
| MCP | stdio MCP Server + Client |
| Tool Use | 7 个工具含闭环 pytest |
| RAG | 分块 BM25 + citation/score |
| Reflexion | 测试失败 → 反思 prompt → 重试 |
| CoT + K-shot | system_prompt.md |
| 多场景泛化 | scenario registry + CLI |

## 技术栈

Python 3.10+ · MCP SDK · OpenAI 兼容 API · pytest
