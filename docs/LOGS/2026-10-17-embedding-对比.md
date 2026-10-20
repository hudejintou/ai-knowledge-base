# 2026-10-17：Embedding 模型对比——Qwen3-Embedding-0.6B 完胜，选型确定

## 今天做了什么

新增 `embedding_model_compare.py`：同一 5 查询 × 5 文档中文语料，对比 Nomic-embed-v1.5 与 Qwen3-Embedding-0.6B（各按官方推荐前缀用法），只依赖 LM Studio 本地服务。

## 关键结果

| 问题（正确文档） | Nomic rank | Qwen3 rank |
|------|-----------|-----------|
| 怎么做缓存？（Redis） | 2 ❌ | 1 ✅ |
| 后台异步跑任务？（Celery） | 1 ✅ | 1 ✅ |
| 数据库表映射 Python 类？（Django） | 2 ❌ | 1 ✅ |
| 打包应用和依赖？（Docker） | 4 ❌ | 1 ✅ |
| 什么是 RAG？ | 1 ✅ | 1 ✅ |

- **Top1 命中：Nomic 2/5 vs Qwen3 5/5**
- **平均 margin（正确文档与最强对手分差）：Nomic +0.015 vs Qwen3 +0.29**——Qwen3 不仅全对，而且分差大一个数量级，排序非常干脆。

## 结论 / 学到的点

1. **主项目 Embedding 选型确定：Qwen3-Embedding-0.6B（LM Studio 本地 GGUF）**。免费、离线、中文强，2026-10-16 的"Nomic 中文弱"结论被定量证实。
2. Qwen3-Embedding 官方用法：文档不加前缀，查询加 `Instruct: {任务}\nQuery: {查询}` 前缀。与 Nomic 的 `search_document:/search_query:` 约定不同，换模型时要注意。
3. Embedding 选型要用自己的真实语料做定量实验，不能只看榜单（Nomic 榜单不差，中文实测拉胯）。
4. 实验 margin 指标曾写错（rank=1 时 margin 恒为 0），修正为"正确文档 vs 最强其他文档"。

## 下一步

- 搭建 `PROJECTS/rag-knowledge-base/` Django/DRF 骨架。
- Embedding 层直接用 Qwen3-Embedding-0.6B（查询加 Instruct 前缀）；智谱 embedding-3 暂不需要（账号也没额度）。
