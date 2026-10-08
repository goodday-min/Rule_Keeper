"""Rule_Keeper MCP 서버 시험용 클라이언트 (설정 파일 없이 검증).

이 스크립트가 MCP 클라이언트 역할을 한다: server.py를 실행하고, MCP 규약(stdio)으로
도구 목록을 받은 뒤 도구를 호출해서 결과를 출력한다. Claude 데스크톱 앱이 하는 일과 같은 흐름이다.

사용법 (backend 폴더, venv 켠 상태):
  python ..\\mcp_server\\test_client.py                                  # 도구 목록 + 오늘 주문
  python ..\\mcp_server\\test_client.py get_portfolio_summary
  python ..\\mcp_server\\test_client.py get_strategy_status "{\\"strategy_id\\": \\"전략id\\"}"
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = Path(__file__).with_name("server.py")


async def main(tool: str, args: dict) -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("== MCP 서버가 알려 준 도구 목록 ==")
            for t in tools.tools:
                print(f"- {t.name}: {(t.description or '').splitlines()[0]}")

            print(f"\n== 도구 호출: {tool}({json.dumps(args, ensure_ascii=False)}) ==")
            result = await session.call_tool(tool, args)
            for c in result.content:
                text = getattr(c, "text", "")
                try:
                    print(json.dumps(json.loads(text), ensure_ascii=False, indent=2))
                except Exception:
                    print(text)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    name = sys.argv[1] if len(sys.argv) > 1 else "get_today_orders"
    arguments = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    asyncio.run(main(name, arguments))
