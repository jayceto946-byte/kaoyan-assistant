#!/usr/bin/env python3
"""📚 考研智能辅助系统 v3.0 — LangGraph 驱动"""
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="📚 考研智能辅助系统 v3.0 — LangGraph Multi-Agent",
        epilog="""
使用示例:
  python main.py cli          命令行界面
  python main.py web          网页界面 (Gradio)
  python main.py web --share  生成公网链接
        """,
    )
    parser.add_argument("mode", nargs="?", default="cli",
                        choices=["cli", "web"],
                        help="启动模式: cli | web")
    parser.add_argument("--port", type=int, default=7860, help="Web端口")
    parser.add_argument("--share", action="store_true", help="公网链接")

    args = parser.parse_args()

    from config import MOONSHOT_API_KEY, OLLAMA_BASE_URL
    if not MOONSHOT_API_KEY:
        print(f"⚠  MOONSHOT_API_KEY 未设置，尝试 Ollama ({OLLAMA_BASE_URL})")
        print("   创建 .env 配置 MOONSHOT_API_KEY (Kimi K2.6)")

    if args.mode == "web":
        import os
        for v in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            os.environ[v] = ""
        from ui.web import StudyWebUI
        ui = StudyWebUI()
        ui.launch(share=args.share, port=args.port)
    else:
        from ui.cli import StudyCLI
        cli = StudyCLI()
        cli.run()


if __name__ == "__main__":
    main()
