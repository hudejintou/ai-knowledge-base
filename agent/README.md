# Agent 小项目：轻量工具调用 Agent

一个不依赖重框架的轻量 Agent。模型可以按需调用工具（天气、计算、读文件），循环有步数与整体时间上限，工具失败时把结构化错误回传给模型，并保存完整的执行轨迹（trace）以便复盘。

本项目与 `backend/`、`rag/` 中的 RAG 主项目相互独立：模型配置、超时与步数上限都单独定义在 `agent/config.py` 中。

## 架构

```
用户问题
   │
   ▼
run_agent（agent/loop.py）
   │  ├─ 调用模型 chat（agent/model.py，智谱 glm-5.3-flash）
   │  │     └─ 返回文本，或返回若干 tool_calls
   │  └─ 有 tool_calls 时，经 ToolRegistry（agent/registry.py）执行
   │        ├─ get_weather  （agent/tools/weather.py，Open-Meteo，真实网络）
   │        ├─ calculate    （agent/tools/calculator.py，AST 安全计算）
   │        └─ read_file    （agent/tools/file_reader.py，白名单目录）
   ▼
{"status", "answer", "trace"}
```

循环规则：

- 一步 = 一次模型调用 + 执行它请求的全部工具。
- 最多 5 步。步数用完后撤掉工具定义，再请求一次最终回答，状态记为 `max_steps`。
- 整体超过 60 秒，不再发起新的模型调用，状态记为 `timeout`。
- 模型不再请求工具时，状态为 `done`。

## 错误处理约定

- 工具的失败都转成结构化字典（`{"error": ..., "message": ...}`），作为 `tool` 消息回传模型，**不抛出异常到循环外**。
- 未知工具名、参数不是合法 JSON、参数名不符合要求，都记为对应错误，循环继续。
- 工具内部的未预期异常被兜底为 `internal`，内部细节不回传给模型。
- 天气工具对超时与 5xx 各重试一次，其他错误不重试。

## Trace

trace 按步骤记录：每一步调用了哪个工具、传入的参数、**完整的返回值**。保存完整内容而非摘要，是为了排错时能判断模型最终回答里的数字来自哪里。

## 目录

| 路径 | 说明 |
| --- | --- |
| `config.py` | 模型名（可由 `AGENT_CHAT_MODEL` 覆盖）、步数与超时上限 |
| `model.py` | 真实模型调用，导入时不连接网络 |
| `registry.py` | 工具注册表 |
| `loop.py` | 通用循环与 trace |
| `tools/` | 三个工具及其 schema |
| `sample_docs/` | `read_file` 的白名单目录 |
| `tests/` | 单元测试（全部 mock，不消耗额度） |
| `run_e2e.py` | 端到端脚本，真实模型，固定 4 条问题 |
| `e2e_runs/` | 端到端运行的 trace 原始文件 |

## 运行

单元测试（不需要网络与额度）：

```bash
docker compose exec web python manage.py test agent.tests -v 2
```

端到端（真实智谱与 Open-Meteo，消耗少量额度）：

```bash
docker compose exec web python -m agent.run_e2e
```

每次运行写入带时间戳的新文件，不覆盖旧结果。

## 已验证的范围

单元测试 33 项通过，覆盖循环、注册表、三个工具的正常与失败路径（mock 网络）。

端到端首次运行（实验 34，见 `docs/EXPERIMENTS.md`）：4 条固定问题，status 均为 `done`，工具选择与参数均正确，数字与工具返回值一致。

## 已知限制

- **回答的依据性不完全可靠**：第 4 条（"火星城"）中，工具返回 `city_not_found`，模型未编造温度，但补充了"可能来自科幻作品"等工具结果之外的推测。这是已记录的偏差，尚未通过提示词实验修正。
- **样本很小**：端到端只有 4 条问题、每条一次运行，不能推断一般可靠性。
- **测试以 mock 为主**：循环逻辑与工具失败路径有单元测试，但真实模型是否会正确选择工具，只有端到端能说明，且样本少。
- **只保存 trace，不保存完整对话**：无法追溯模型某一轮的原始输出。
- **`calculate` 只支持四则运算**，不支持函数与幂运算。
- **`read_file` 只能读取白名单目录下的小文本文件**（上限 64KB，UTF-8）。
- **天气数据来自 Open-Meteo 的公开接口**，依赖外网，偶发超时会返回 `timeout`。
- **无并发与持久化**：每次运行都是独立进程，没有会话记忆。

## 后续可选方向

- 用新版系统提示词（约束"只依据工具结果"）做对照实验，运行前写明判断规则，结果另存。
- 为 trace 增加完整对话记录，便于定位模型在哪一轮产生了推测。
- 增加更多固定问题，扩大端到端样本，并预先写明判断标准。