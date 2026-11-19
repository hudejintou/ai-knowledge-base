"""Agent 小项目的配置，与 backend/qa/config.py 独立。"""

import os

# 模型名单独配置，可用环境变量覆盖
CHAT_MODEL = os.getenv("AGENT_CHAT_MODEL", "glm-5.3-flash")

MAX_STEPS = 5             # 一步 = 一次模型调用 + 执行它请求的全部工具
OVERALL_TIMEOUT = 60      # 整体上限（秒），超过后不再发起新的模型调用
MODEL_CALL_TIMEOUT = 20   # 单次模型调用超时（秒）