# ai-demo

基于智谱 GLM 大模型的 Python 示例，演示**真实流式输出**与**Function Calling（工具调用）**两个核心能力。

## 功能

- **流式输出**：调用模型并以逐字方式实时打印返回内容。
- **Function Calling**：
  - `get_weather`：查询指定城市的当前天气（示例中使用假数据）。
  - `calculate`：安全计算数学表达式，支持 `+ - * /`、括号和负号（基于 `ast` 安全求值，不使用 `eval`）。
  - 支持模型自主决定是否调用工具，以及多步连续调用。

## 环境要求

- Python 3.8+
- 一个可用的智谱 AI（BigModel）API Key

## 安装

```bash
pip install openai
```

## 配置

通过环境变量提供 API Key（**请勿把密钥写进代码或提交到仓库**）：

```bash
export ZHIPU_API_KEY="你的智谱 API Key"
```

模型名称在代码中通过 `MODEL` 常量配置，请以你账号实际可用的模型名为准。

## 使用

```bash
python test.py
```

运行后会依次执行若干示例：流式解释 RAG、查询天气、普通对话、数学计算，以及多步工具调用等。

## 代码结构

| 函数 | 说明 |
| --- | --- |
| `stream_chat(prompt)` | 流式对话输出 |
| `get_weather(location)` | 天气查询工具（示例假数据） |
| `calculate(expression)` | 安全的数学表达式计算工具 |
| `chat_with_tools(question, max_rounds)` | 带工具调用的多轮对话主循环 |
