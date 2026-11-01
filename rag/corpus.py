# corpus.py
# 语料：每条是一个独立知识片段，主题互相有一定重叠，避免过于容易区分。
DOCS = [
    "Redis 是基于内存的键值数据库。常见用途是做缓存：把热点数据放进 Redis，设置过期时间，减少数据库查询压力。",
    "Redis 支持持久化，RDB 是定时快照，AOF 记录每条写命令，两者可以结合使用以降低数据丢失风险。",
    "Redis 的 String、Hash、List、Set、ZSet 是常用的数据类型，其中 ZSet 适合做排行榜。",
    "Celery 是 Python 的分布式任务队列。适合处理耗时任务，如发送邮件、生成报表，通过 Redis 或 RabbitMQ 作为消息中间件异步执行。",
    "Celery Beat 是 Celery 的定时任务组件，可以按固定间隔或 crontab 规则周期性地触发任务。",
    "Django ORM 把数据库表映射成 Python 类。通过 Model 定义字段，用 QuerySet 查询，避免手写 SQL。",
    "Django 的 Migration 机制根据 Model 的变化生成迁移文件，用 makemigrations 生成，用 migrate 应用到数据库。",
    "Django REST Framework 提供 Serializer 用于数据校验和序列化，可以声明字段类型和约束，并在 validate 方法里做自定义校验；ViewSet 用于组织增删改查接口。",
    "Docker 用容器打包应用及其依赖。通过 Dockerfile 构建镜像，镜像运行后得到容器。",
    "docker-compose 用一个 YAML 文件定义多个服务及其网络和卷，可以一条命令启动整套环境。",
    "PostgreSQL 是功能完整的关系型数据库，支持 JSON 字段和扩展插件，pgvector 扩展可以存储和检索向量。",
    "MySQL 的 InnoDB 引擎支持事务和行级锁，索引通常采用 B+ 树结构。",
    "数据库索引能加快查询速度，但会增加写入开销和存储空间，应针对高频查询的字段建立索引。",
    "RAG 先检索相关文档，再让大模型基于文档回答，用来减少幻觉并接入私有知识。",
    "文本切分（chunking）是 RAG 的关键步骤。常见做法是按 300 到 800 个字符切块，并在相邻块之间保留一定重叠，避免语义被切断。切得太大会引入无关内容，切得太小会丢失上下文。",
    "Embedding 把文本转换为向量，语义相近的文本在向量空间中距离更近，常用余弦相似度衡量。",
    "向量数据库负责存储向量并做近似最近邻检索，Chroma 适合本地小规模实验，pgvector 可以直接复用 PostgreSQL。",
    "Function Calling 让大模型根据工具的 JSON Schema 决定是否调用工具以及传入的参数，开发者执行后把结果回传给模型。",
    "Prompt 中明确要求模型只依据给定资料回答，可以减少模型补充资料外内容的情况，但不能完全消除。",
    "Git 的 rebase 会把当前分支的提交移到另一个分支的最新提交之后，使提交历史呈线性，但不应对已推送的公共分支使用。",
]

# 评估集：question 是用户问题，relevant 是应当被检索到的文档在 DOCS 中的下标。
# 无关问题的 relevant 为空列表，表示正确结果是拒答。
EVAL_SET = [
    {"question": "怎么做缓存？", "relevant": [0]},
    {"question": "Redis 数据怎么持久化？", "relevant": [1]},
    {"question": "排行榜用 Redis 的哪种数据类型？", "relevant": [2]},
    {"question": "后台异步跑任务用什么？", "relevant": [3]},
    {"question": "怎么定时执行任务？", "relevant": [4]},
    {"question": "Python 怎么操作数据库表？", "relevant": [5]},
    {"question": "数据库表结构变更怎么同步？", "relevant": [6]},
    {"question": "怎么做接口的数据校验？", "relevant": [7]},
    {"question": "怎么把应用和依赖打包？", "relevant": [8]},
    {"question": "怎样一条命令启动多个服务？", "relevant": [9]},
    {"question": "能存向量的 PostgreSQL 插件是什么？", "relevant": [10]},
    {"question": "MySQL 用什么索引结构？", "relevant": [11]},
    {"question": "给表加索引有什么代价？", "relevant": [12]},
    {"question": "RAG 解决什么问题？", "relevant": [13]},
    {"question": "文档切多大比较合适？", "relevant": [14]},
    {"question": "文本怎么变成可比较的向量？", "relevant": [15]},
    {"question": "本地小规模实验用哪个向量库？", "relevant": [16]},
    {"question": "大模型怎么调用外部工具？", "relevant": [17]},
    {"question": "怎样减少模型编造资料外的内容？", "relevant": [18]},
    {"question": "Git 变基会有什么影响？", "relevant": [19]},
    {"question": "今天股市怎么样？", "relevant": []},
    {"question": "明天会下雨吗？", "relevant": []},
    {"question": "今天中午吃什么比较好？", "relevant": []},
    {"question": "推荐一部好看的电影", "relevant": []},
    # 近邻但语料没有答案：主题相近，应拒答
    {"question": "Redis 集群怎么搭建？", "relevant": []},
    {"question": "Redis 主从复制怎么配置？", "relevant": []},
    {"question": "Celery 任务失败后怎么重试？", "relevant": []},
    {"question": "Django 怎么做用户登录认证？", "relevant": []},
    {"question": "Django 怎么配置缓存中间件？", "relevant": []},
    {"question": "Docker 怎么把镜像推送到仓库？", "relevant": []},
    {"question": "PostgreSQL 怎么做主从备份？", "relevant": []},
    {"question": "MySQL 的慢查询怎么排查？", "relevant": []},
    {"question": "RAG 的 Reranker 怎么选型？", "relevant": []},
    {"question": "Function Calling 怎么做参数校验？", "relevant": []},
    {"question": "Git 怎么撤销一次提交？", "relevant": []},
    {"question": "Embedding 模型怎么微调？", "relevant": []},
]
# 留出测试集：只用于最终评估，不根据结果修改语料或 Prompt
HOLDOUT_SET = [
    # 可回答
    {"question": "Redis 拿来当缓存用时要注意什么？", "relevant": [0]},
    {"question": "Celery 能帮忙做哪类耗时工作？", "relevant": [3]},
    {"question": "ORM 的作用是什么？", "relevant": [5]},
    {"question": "Docker 镜像和容器的关系是什么？", "relevant": [8]},
    {"question": "文本切块时块大小怎么选？", "relevant": [14]},
    {"question": "大模型怎么获得外部数据的访问能力？", "relevant": [17]},
    # 无关 / 近邻无答案
    {"question": "Redis 怎么做分布式锁？", "relevant": []},
    {"question": "这周末天气怎么样？", "relevant": []},
    {"question": "Django 怎么部署到 Nginx？", "relevant": []},
    {"question": "Docker 怎么限制容器内存？", "relevant": []},
]
# 多跳与间接说法题集：冻结后不得根据结果修改。
# relevant：回答所需的全部资料下标（DOCS 中的位置），空列表表示应拒答。
MULTI_SET = [
    # 多跳：答案分散在两份资料里
    {"question": "用 Celery 做定时任务时，消息一般通过什么中间件转发？", "relevant": [3, 4]},
    {"question": "MySQL 加索引好不好，代价是什么，它用什么数据结构？", "relevant": [11, 12]},
    {"question": "向量数据库和 PostgreSQL 能不能结合使用？", "relevant": [10, 16]},
    {"question": "用一个配置文件同时启动多个服务，服务的运行环境是怎么打包的？", "relevant": [9, 8]},
    {"question": "为了防止模型乱编，除了接入资料还能在提示词里做什么？", "relevant": [18, 13]},
    # 间接说法：问题用词与资料差异大
    {"question": "我的网站每次都从数据库读同样的数据，怎么减轻数据库压力？", "relevant": [0]},
    {"question": "想让 Redis 重启后数据还在，应该怎么做？", "relevant": [1]},
    {"question": "不想手写 SQL 就能操作数据库，有什么方式？", "relevant": [5]},
    {"question": "数据库表改了结构，之后怎么同步到真实库？", "relevant": [6]},
    {"question": "让大模型能查外部系统，它是怎么决定调用哪个工具的？", "relevant": [17]},
    # 近邻拒答：主题相近但语料没有答案
    {"question": "用 Kafka 做消息队列和 Celery 相比哪个更好？", "relevant": []},
    {"question": "Redis 的 Cluster 模式怎么扩容？", "relevant": []},
    {"question": "帮我写一个 Python 爬虫抓取股票价格", "relevant": []},
    {"question": "Django 项目怎么接入 Kubernetes 做自动扩缩容？", "relevant": []},
]
# ===== 扩充语料（阶段 E 之后）=====
# 原 DOCS 的 20 条保持不变，评估题集的 relevant 下标依赖它。
# 扩充语料放在 rag/data/corpus_v3.txt，按空行切段，追加在 DOCS 之后。
from pathlib import Path as _Path

_EXT_PATH = _Path(__file__).resolve().parent / "data" / "corpus_v3.txt"
DOCS_EXT = [p.strip() for p in _EXT_PATH.read_text(encoding="utf-8").split("\n\n") if p.strip()]

# 入库使用的完整语料：前 20 条是 DOCS，之后是扩充段落（下标 20 起）
ALL_DOCS = DOCS + DOCS_EXT
