"""命令行问答入口：循环读取问题 -> 调用 answer_with_judgement -> 打印结果。

运行方式（必须在项目根目录，用 python -m 运行）：
    cd /Users/zhanglun/project/AI
    python -m rag.chat

运行前提：
1. LM Studio 已启动本地服务，并加载 text-embedding-qwen3-embedding-0.6b；
2. 环境变量 ZHIPU_API_KEY 已设置（rag_v1.py 导入时会读取）。
"""

# 注意：这里导入 rag_v1 时会立即连接 LM Studio 并计算文档向量（见 rag_v1.py 的 DOC_VECS）。
# 所以 LM Studio 没启动时，程序会在这一行就报错，还进不了问答循环。
from rag.rag_v1 import answer_with_judgement  # 只用这一个函数，与评估脚本保持一致

# 退出指令用集合存放，用 set 判断"是否在集合里"很快，以后加别名也只改这一处
EXIT_COMMANDS = {"q", "quit", "exit"}


def ask_once(question):
    """问一个问题，返回要打印的文字。单独拆成函数，便于以后写测试。"""
    refused, text = answer_with_judgement(question)

    # 关键：是否拒答只看 refused 这个布尔值，不看 text 的内容。
    # 模型输出可能是 "[NO_ANSWER]"，也可能是 "[NO_ANSWER] 资料中..." 这类夹杂文字，
    # 所以不要自己再去字符串匹配一次，直接信任 refused。
    if refused:
        return "[拒答] 资料中没有足够信息回答这个问题。"
    return f"[回答] {text}"


def main():
    print("企业知识库问答（输入 q 退出）")
    while True:
        try:
            # strip() 去掉首尾空白，避免只输入空格也被当成问题
            question = input("\n问题> ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+D 或 Ctrl+C 属于用户主动结束，打印一句告别即可，不要抛出堆栈
            print("\n再见")
            break

        if not question:
            continue  # 空输入直接跳过，不调用模型，省时间也省智谱额度

        if question.lower() in EXIT_COMMANDS:
            print("再见")
            break

        try:
            print(ask_once(question))
        except Exception as exc:
            # 关键：问答过程里的任何错误（网络超时、智谱 Key 错误、LM Studio 中途关闭）
            # 都在这里被捕获，程序不退出，用户可以继续问。
            # 代价：这里用的是宽泛的 Exception，调试时如果想看完整堆栈，可以临时去掉 try。
            print(f"[错误] {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()