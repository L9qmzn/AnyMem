#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI 搜索测试工具
用法: python dev_tests/test_search_cli.py [查询词]

交互模式: python dev_tests/test_search_cli.py
"""
import sys
import io
import requests
import json
import time

# Windows 控制台 UTF-8 支持
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

AI_SERVICE_URL = "http://localhost:8000"


def get_available_retrievers():
    """获取可用的检索策略"""
    try:
        response = requests.get(f"{AI_SERVICE_URL}/internal/search/retrievers", timeout=10)
        response.raise_for_status()
        return response.json().get("retrievers", [])
    except Exception:
        return []


def search(
    query: str,
    top_k: int = 10,
    search_mode: str = "hybrid",
    min_score: float = 0.0,
    alpha: float = 0.5,
    rrf_k: int = 60,
    bm25_weight: float = 1.0,
    vector_weight: float = 1.0,
):
    """执行搜索，返回 (结果, 响应时间ms)"""
    start_time = time.time()

    try:
        response = requests.post(
            f"{AI_SERVICE_URL}/internal/search",
            json={
                "query": query,
                "top_k": top_k,
                "search_mode": search_mode,
                "min_score": min_score,
                "alpha": alpha,
                "rrf_k": rrf_k,
                "bm25_weight": bm25_weight,
                "vector_weight": vector_weight,
            },
            timeout=30,
        )
        elapsed_ms = (time.time() - start_time) * 1000

        response.raise_for_status()
        result = response.json()
        result["_elapsed_ms"] = elapsed_ms
        return result
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到 AI 服务 ({AI_SERVICE_URL})")
        print("   请确保 AI 服务正在运行: python -m ai_parts.main")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 错误: {e}")
        try:
            print(f"   详情: {e.response.json()}")
        except Exception:
            pass
        return None
    except Exception as e:
        print(f"❌ 搜索失败: {e}")
        return None


def print_results(data: dict):
    """打印搜索结果"""
    if not data:
        return

    elapsed_ms = data.get("_elapsed_ms", 0)
    print(f"\n{'='*60}")
    print(f"查询: {data['query']}")
    print(f"策略: {data.get('search_mode', 'unknown')}")
    print(f"结果数: {data['total']}")
    print(f"耗时: {elapsed_ms:.0f} ms")
    print(f"{'='*60}\n")

    for i, result in enumerate(data["results"], 1):
        score = result["score"]
        memo_name = result["memo_name"]
        content = result["content"]
        metadata = result.get("metadata", {})
        source = result.get("source", "text")

        # 截断长内容
        if len(content) > 200:
            content = content[:200] + "..."

        print(f"[{i}] 分数: {score:.4f} ({source})")
        print(f"    Memo: {memo_name}")

        # 显示标签
        tags = metadata.get("tags", "")
        if tags:
            print(f"    标签: {tags}")

        # 显示附件信息（如果有）
        if "filename" in metadata:
            print(f"    附件: {metadata['filename']} ({metadata.get('type', 'unknown')})")

        print(f"    内容: {content}")
        print()


def print_help():
    """打印帮助信息"""
    print("""
命令:
  输入查询词进行搜索

  :mode <策略>     - 切换检索策略
  :list            - 列出所有可用策略
  :top N           - 设置返回结果数
  :min N           - 设置最低分数阈值
  :alpha N         - 设置 alpha 权重 (0=BM25, 1=向量)
  :rrf N           - 设置 RRF k 参数
  :compare <q>     - 对比多种策略的结果
  :help            - 显示帮助
  :quit 或 :q      - 退出

可用策略:
  基础: text, image, vector
  混合: hybrid, rrf, weighted
  BM25: bm25, bm25_vector, bm25_vector_alpha, adaptive
""")


def compare_strategies(query: str, strategies: list, top_k: int = 5, **kwargs):
    """对比多种策略的搜索结果"""
    print(f"\n{'='*60}")
    print(f"策略对比: {query}")
    print(f"{'='*60}")

    results_with_time = []
    for strategy in strategies:
        result = search(query, top_k=top_k, search_mode=strategy, **kwargs)
        if result:
            elapsed_ms = result.get("_elapsed_ms", 0)
            print(f"\n【{strategy}】 {result['total']} 条结果 ({elapsed_ms:.0f} ms):")
            for i, r in enumerate(result["results"][:3], 1):
                content = r["content"][:80] + "..." if len(r["content"]) > 80 else r["content"]
                content = content.replace("\n", " ")
                print(f"  {i}. [{r['score']:.3f}] {content}")
            results_with_time.append((strategy, elapsed_ms))
        else:
            print(f"\n【{strategy}】 搜索失败")

    # 显示时间对比
    if results_with_time:
        print(f"\n{'='*60}")
        print("响应时间对比:")
        results_with_time.sort(key=lambda x: x[1])
        for strategy, elapsed_ms in results_with_time:
            print(f"  {strategy:20} {elapsed_ms:6.0f} ms")
        print(f"{'='*60}")


def interactive_mode():
    """交互模式"""
    print("="*60)
    print("AI 搜索测试工具 (支持 BM25 + Vector 混合检索)")
    print("="*60)

    # 获取可用策略
    retrievers = get_available_retrievers()
    if retrievers:
        print(f"可用策略: {', '.join(r['name'] for r in retrievers)}")
    else:
        print("提示: 无法获取策略列表，服务可能未启动")

    print("输入 :help 查看帮助")
    print("="*60)

    # 默认参数
    search_mode = "hybrid"
    top_k = 10
    min_score = 0.0
    alpha = 0.5
    rrf_k = 60
    bm25_weight = 1.0
    vector_weight = 1.0

    while True:
        try:
            query = input(f"\n[{search_mode}] 搜索> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见！")
            break

        if not query:
            continue

        # 处理命令
        if query.startswith(":"):
            parts = query.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd in (":quit", ":q"):
                print("再见！")
                break

            elif cmd == ":help":
                print_help()

            elif cmd == ":list":
                retrievers = get_available_retrievers()
                if retrievers:
                    print("\n可用检索策略:")
                    for r in retrievers:
                        print(f"  {r['name']:20} - {r['description']}")
                else:
                    print("无法获取策略列表")

            elif cmd == ":mode":
                if arg:
                    search_mode = arg.lower()
                    print(f"检索策略已切换为: {search_mode}")
                else:
                    print(f"当前策略: {search_mode}")
                    print("用法: :mode <策略名>")

            elif cmd == ":top":
                try:
                    top_k = int(arg)
                    print(f"返回结果数已设置为: {top_k}")
                except ValueError:
                    print(f"当前: {top_k}，用法: :top N")

            elif cmd == ":min":
                try:
                    min_score = float(arg)
                    print(f"最低分数阈值已设置为: {min_score}")
                except ValueError:
                    print(f"当前: {min_score}，用法: :min N")

            elif cmd == ":alpha":
                try:
                    alpha = float(arg)
                    print(f"Alpha 权重已设置为: {alpha} (0=BM25, 1=向量)")
                except ValueError:
                    print(f"当前: {alpha}，用法: :alpha N (0.0-1.0)")

            elif cmd == ":rrf":
                try:
                    rrf_k = int(arg)
                    print(f"RRF k 参数已设置为: {rrf_k}")
                except ValueError:
                    print(f"当前: {rrf_k}，用法: :rrf N")

            elif cmd == ":compare":
                if arg:
                    strategies = ["text", "bm25", "bm25_vector", "adaptive"]
                    compare_strategies(
                        arg, strategies, top_k=5,
                        alpha=alpha, rrf_k=rrf_k,
                        bm25_weight=bm25_weight, vector_weight=vector_weight
                    )
                else:
                    print("用法: :compare <查询词>")

            else:
                print(f"未知命令: {cmd}，输入 :help 查看帮助")
            continue

        # 执行搜索
        result = search(
            query,
            top_k=top_k,
            search_mode=search_mode,
            min_score=min_score,
            alpha=alpha,
            rrf_k=rrf_k,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
        )
        print_results(result)


def main():
    if len(sys.argv) > 1:
        # 命令行模式
        query = " ".join(sys.argv[1:])
        result = search(query)
        print_results(result)
    else:
        # 交互模式
        interactive_mode()


if __name__ == "__main__":
    main()
