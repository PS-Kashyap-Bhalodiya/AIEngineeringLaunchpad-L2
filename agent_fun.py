import asyncio
import json
import sys
from typing import Dict, Any, List
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ollama import chat  # pip install ollama

SYSTEM = """You are a cheerful weekend helper with access to MCP tools.

CRITICAL RULES:
1. Return ONLY ONE valid JSON object per response
2. Never return multiple JSON objects
3. Never add explanations or markdown
4. Just pure JSON

WORKFLOW:
- User asks a question
- You return ONE JSON action (tool call OR final answer)
- If you called a tool, you'll see its result
- Then you decide next action (another tool OR final answer)
- Repeat until you have all info, then give final answer

JSON FORMATS (use exactly one):
Tool call: {"action":"tool_name","args":{"param":"value"}}
Final answer: {"action":"final","answer":"your response"}

EXAMPLE - User: "tell me a joke and recommend a book"
Step 1: {"action":"random_joke","args":{}}
Step 2: [you see joke result]
Step 3: {"action":"book_recs","args":{"topic":"general","limit":3}}
Step 4: [you see book results]
Step 5: {"action":"final","answer":"Here's a joke: [joke]. And book recommendations: [books]"}

Remember: ONE JSON object only. No explanations."""


def llm_json(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    resp = chat(model="mistral:7b", messages=messages, options={"temperature": 0.2})
    txt = resp["message"]["content"].strip()
    
    # Try to parse as JSON first
    try:
        return json.loads(txt)
    except Exception:
        # Check if it looks like a natural language answer (no JSON structure at all)
        if not txt.startswith("{") and "action" not in txt:
            return {"action": "final", "answer": txt}
        
        # Try to extract just the first JSON object if multiple were returned
        if txt.count("{") > 1:
            try:
                # Find first complete JSON object
                start = txt.find("{")
                brace_count = 0
                for i in range(start, len(txt)):
                    if txt[i] == "{":
                        brace_count += 1
                    elif txt[i] == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            first_json = txt[start:i+1]
                            return json.loads(first_json)
            except Exception:
                pass
        
        # Try to fix malformed JSON with a second LLM call
        try:
            fix_prompt = (
                "Convert the following text into ONLY this exact JSON format: "
                '{"action":"final","answer":"<text>"} '
                "Return ONLY the JSON, nothing else."
            )
            fix = chat(model="mistral:7b",
                       messages=[{"role": "system", "content": fix_prompt},
                                 {"role": "user", "content": txt}],
                       options={"temperature": 0})
            fixed_txt = fix["message"]["content"].strip()
            return json.loads(fixed_txt)
        except Exception:
            # Last resort: wrap whatever we got in a final answer
            return {"action": "final", "answer": txt}


async def main():
    server_path = sys.argv[1] if len(sys.argv) > 1 else "server_fun.py"
    exit_stack = AsyncExitStack()
    stdio = await exit_stack.enter_async_context(
        stdio_client(StdioServerParameters(command="python", args=[server_path]))
    )
    r_in, w_out = stdio
    session = await exit_stack.enter_async_context(ClientSession(r_in, w_out))
    await session.initialize()

    tools = (await session.list_tools()).tools
    tool_index = {t.name: t for t in tools}
    print("Connected tools:", list(tool_index.keys()))

    # Build detailed tool schemas for the system prompt
    tool_schemas = []
    for t in tools:
        schema = f"- {t.name}: {t.description}"
        if t.inputSchema and "properties" in t.inputSchema:
            params = []
            required = t.inputSchema.get("required", [])
            for param_name, param_info in t.inputSchema["properties"].items():
                param_type = param_info.get("type", "any")
                is_required = param_name in required
                req_marker = " (required)" if is_required else " (optional)"
                params.append(f"    - {param_name}: {param_type}{req_marker}")
            if params:
                schema += "\n" + "\n".join(params)
        tool_schemas.append(schema)
    
    tool_desc = "\n".join(tool_schemas)
    system_with_tools = SYSTEM + f"\n\nAvailable tools:\n{tool_desc}"
    
    history = [{"role": "system", "content": system_with_tools}]
    try:
        while True:
            user = input("\nYou: ").strip()
            if not user or user.lower() in {"exit", "quit"}:
                break
            history.append({"role": "user", "content": user})

            for iteration in range(6):  # increased for multi-step requests
                try:
                    decision = llm_json(history)
                except Exception as e:
                    print(f"[ERROR] Failed to get valid JSON from LLM: {e}")
                    break
                    
                if decision.get("action") == "final":
                    answer = decision.get("answer", "")
                    print("\nAgent:", answer)
                    history.append({"role": "assistant", "content": answer})
                    break

                tname = decision.get("action")
                args = decision.get("args", {})
                if tname not in tool_index:
                    print(f"[ERROR] Unknown tool: {tname}")
                    history.append({"role": "assistant", "content": f"(unknown tool {tname})"})
                    continue

                try:
                    # Tool calls are made here (without debug prints as requested)
                    result = await session.call_tool(tname, args)
                    payload = result.content[0].text if result.content else result.model_dump_json()
                    history.append({"role": "assistant", "content": f"[tool:{tname}] {payload}"})
                except Exception as e:
                    error_msg = f"Tool call failed: {e}"
                    print(f"[ERROR] {error_msg}")
                    history.append({"role": "assistant", "content": f"[error] {error_msg}"})
    finally:
        await exit_stack.aclose()


if __name__ == "__main__":
    asyncio.run(main())