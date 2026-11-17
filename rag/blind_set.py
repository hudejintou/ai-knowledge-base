# rag/blind_set.py
# 预注册题集（非严格盲测）：出题时已阅读语料，题目在评估前冻结。
# 冻结后不得修改题目或 relevant。relevant 为 ALL_DOCS 的下标。
# 扩充段下标 = 20 + 段号。

BLIND_SET = [
    # ---- 单段可答：RAG 原始论文（下标 20–25）----
    {"question": "纯参数化模型有哪两个长期未解决的问题？", "relevant": [20]},
    {"question": "RAG 中负责生成语言的那部分记忆是什么形式？", "relevant": [21]},
    {"question": "一个输出序列能否在生成中途切换到另一份检索文档取材？", "relevant": [22]},
    {"question": "原论文把维基百科切成多长的段落，文档数量大约多少？", "relevant": [23]},
    {"question": "论文在 FEVER 事实核查任务上与强检索流水线的差距是多少？", "relevant": [24]},
    {"question": "为什么不必重新训练参数，就能更新模型掌握的知识？", "relevant": [25]},

    # ---- 单段可答：OpenAI 嵌入指南（下标 26–31）----
    {"question": "嵌入的核心用途是度量什么？", "relevant": [26]},
    {"question": "余弦相似度为 0 通常意味着什么？", "relevant": [27]},
    {"question": "text-embedding-3-small 在 MTEB 基准上的得分是多少？", "relevant": [28]},
    {"question": "把 text-embedding-3-large 截断到 256 维，与哪个模型相比仍然更好？", "relevant": [29]},
    {"question": "嵌入的应用中，异常检测指的是什么？", "relevant": [30]},
    {"question": "两个不同嵌入模型生成的向量混用，会造成什么后果？", "relevant": [31]},

    # ---- 单段可答：Anthropic Contextual Retrieval（下标 32–37）----
    {"question": "为什么嵌入模型之外还建议配合 BM25 使用？", "relevant": [32]},
    {"question": "单个块脱离原语境时，检索器为什么难以把它和问题对上？", "relevant": [33]},
    {"question": "为每个块生成上下文说明时，靠什么降低成本？", "relevant": [34]},
    {"question": "上下文化嵌入加上下文化 BM25 后，top-20 失败率从多少降到多少？", "relevant": [35]},
    {"question": "重排序模型在流程中处理多少候选、保留多少个结果？", "relevant": [36]},
    {"question": "为特定领域定制上下文生成的提示词时，加入什么内容往往效果更好？", "relevant": [37]},

    # ---- 单段可答：Microsoft Learn RAG（下标 38–43）----
    {"question": "用自有内容给 LLM 响应接地，主要能缓解哪两类问题？", "relevant": [38]},
    {"question": "企业内容散落在多个平台，会给 RAG 带来什么挑战？", "relevant": [39]},
    {"question": "代理式检索返回的结果中内置了哪些配套信息？", "relevant": [40]},
    {"question": "经典 RAG 模式的主要优点是什么？", "relevant": [40]},
    {"question": "混合检索中，关键词路径和向量路径的结果如何合并？", "relevant": [41]},
    {"question": "需要对查询管线做细粒度控制时，应选哪种模式？", "relevant": [43]},
    {"question": "页面认为 RAG 的效果取决于哪三方面的组合？", "relevant": [42]},

    # ---- 跨段题（需要两段信息）----
    {"question": "纯参数化模型的局限，与 RAG 如何通过索引更新知识，两者的对应关系是什么？", "relevant": [20, 25]},
    {"question": "余弦相似度的含义，以及嵌入模型必须一致的要求，分别是什么？", "relevant": [27, 31]},
    {"question": "代理式检索与经典 RAG 各自适合什么场景？", "relevant": [40, 43]},
    {"question": "上下文化处理降低了多少失败率，重排序又在此基础上起什么作用？", "relevant": [35, 36]},

    # ---- 近邻拒答（语料中没有答案）----
    {"question": "Anthropic 的上下文生成是否用过 GPT-4？", "relevant": []},
    {"question": "Azure AI Search 的收费标准是多少？", "relevant": []},
    {"question": "Lewis 论文中 BART 生成器的参数量是多少？", "relevant": []},
    {"question": "OpenAI 嵌入 API 的请求频率限制是多少？", "relevant": []},
    {"question": "Voyage 嵌入模型每百万 token 的价格是多少？", "relevant": []},
    {"question": "如何在 Azure 中为 SharePoint 文档配置用户权限？", "relevant": []},
    {"question": "Milvus 的分布式部署需要哪些组件？", "relevant": []},
]