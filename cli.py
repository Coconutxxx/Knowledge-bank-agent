"""命令行入口：导入文档或连续问答。"""

from __future__ import annotations

import argparse

from src.core.agent import KnowledgeAgent
from src.rag.indexer import KnowledgeIndexer
from src.rag.vector_store import VectorStore


def ingest_command(path: str) -> None:
    store = VectorStore()
    result = KnowledgeIndexer(store).ingest(path)
    print(
        f"导入完成：{result['files']} 个文件，"
        f"{result['sections']} 个文档段，{result['chunks']} 个文本块。"
    )
    print(f"知识库当前共 {store.count()} 个文本块。")


def chat_command() -> None:
    agent = KnowledgeAgent()
    print("知识库 Agent 已启动。输入 quit 退出，reset 清空对话记忆。")
    while True:
        try:
            question = input("\n你：").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见。")
            return
        if not question:
            continue
        if question.lower() == "quit":
            return
        if question.lower() == "reset":
            agent.reset_memory()
            print("对话记忆已清空。")
            continue
        result = agent.run(question)
        print(f"\nAgent：{result.answer}")
        if result.sources:
            print("\n检索来源：")
            for number, source in enumerate(result.sources, start=1):
                print(f"  {number}. {source.citation}")


def main() -> None:
    parser = argparse.ArgumentParser(description="本地知识库问答 Agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest", help="导入文件或文件夹")
    ingest_parser.add_argument("path", help="文件或文件夹路径")
    subparsers.add_parser("chat", help="启动命令行问答")
    args = parser.parse_args()
    if args.command == "ingest":
        ingest_command(args.path)
    else:
        chat_command()


if __name__ == "__main__":
    main()

