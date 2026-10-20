# CLAUDE.md（工作区使用说明）

> 本文件告诉 AI 助手如何使用这套工作区。**最重要的一条：会话开始只读 2 个文件，不要全量重读。**

## 会话启动规则（省积分的关键）

1. **必读（仅 2 个）**：`docs/PROJECTS/README.md`（项目当前状态+待办）+ `docs/MEMORY/AI_ROADMAP.md` 的「当前位置」部分。
2. **按需再读**：涉及目标读 LONG_TERM_GOALS；涉及协作方式读 PREFERENCES；涉及背景读 PERSONAL_PROFILE；具体实验数据读 docs/EXPERIMENTS.md；历史过程读 docs/LOGS/。
3. 不要每次会话通读全部文档；LOGS 是唯一事实源，其他文件只放状态和链接。

## 目录结构

```
AI/
├── rag/            # 核心模块（rag_v1.py、corpus.py、chat.py）
├── evals/          # 评估脚本 + runs/（结果 JSON）
├── experiments/    # 一次性实验脚本
├── backend/        # Django/DRF 后端（阶段 B）
├── docs/
│   ├── MEMORY/     # 长期记忆：PERSONAL_PROFILE / LONG_TERM_GOALS / AI_ROADMAP / PREFERENCES
│   ├── PROJECTS/   # 项目状态索引（当前状态+待办，一页纸）
│   ├── LOGS/       # 唯一事实源：按日期日志；workbuddy/ 为 AI 会话记录归档
│   └── EXPERIMENTS.md  # 实验记录（变量/结果/结论）
├── CLAUDE.md       # 本文件
└── README.md       # 仓库说明
```

## 信息归属原则（一个事实只有一个家）

| 信息 | 唯一存放处 |
|------|-----------|
| 我是谁/设备/技术底子 | docs/MEMORY/PERSONAL_PROFILE.md |
| 职业目标/里程碑/项目范围 | docs/MEMORY/LONG_TERM_GOALS.md |
| 当前阶段/排期/验收标准/JD 对标 | docs/MEMORY/AI_ROADMAP.md |
| 学习与协作偏好/模型选型表 | docs/MEMORY/PREFERENCES.md |
| 发生了什么（按日期） | docs/LOGS/YYYY-MM-DD-*.md |
| 实验数据与结论 | docs/EXPERIMENTS.md |
| 项目当前状态+待办 | docs/PROJECTS/README.md |

- 更新进展时：**写 LOGS + 刷新 PROJECTS/README 状态 + 勾选 ROADMAP 对应项**，不要在多处复述细节。
- 长期有效信息才进 MEMORY；临时过程进 LOGS；重要技术决策（选型/架构/踩坑）记入 LOGS。
- 新建文件前先检查是否已存在；文件用 Markdown、简洁结构化。
- 不要大规模下载模型、不要修改 Conda/系统环境（除非用户明确要求）；不要要求用户粘贴 API Key。
