import asyncio
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.models.schemas import SseMessage
from app.session.manager import session_store

router = APIRouter()


@router.get("/ai_ops/templates")
async def get_templates():
    from app.agent.task_templates import TASK_TEMPLATES
    return [{"key": k, "label": v["label"], "icon": v["icon"]}
            for k, v in TASK_TEMPLATES.items()]


@router.post("/ai_ops/template/{template_key}")
async def run_template(request: Request, template_key: str):
    from app.agent.task_templates import TASK_TEMPLATES
    template = TASK_TEMPLATES.get(template_key)
    if not template:
        return {"error": "unknown template"}
    supervisor = request.app.state.supervisor
    result = await supervisor.invoke(template["prompt"])
    return {"answer": result}

SRE_TASK = (
    "你是企业级 SRE，接到了自动化告警排查任务。"
    "请先查询当前活跃的 Prometheus 告警，然后查询相关日志和知识库，"
    "进行根因分析，并最终按照固定模板输出《告警分析报告》。"
    "禁止编造虚假数据，如连续多次查询失败需诚实反馈无法完成的原因。"
)


@router.post("/ai_ops")
async def ai_ops(request: Request):
    supervisor = request.app.state.supervisor

    async def event_stream():
        start_msg = SseMessage(type="content", data="正在启动 SRE 告警排查...\n")
        yield f"event: message\ndata: {json.dumps(start_msg.model_dump(), ensure_ascii=False)}\n\n"

        try:
            final_content = ""
            async for event in supervisor.astream(SRE_TASK):
                msgs = event.get("messages", [])
                if msgs:
                    last = msgs[-1]
                    content = getattr(last, "content", "") or ""
                    msg_type = getattr(last, "type", "")

                    if hasattr(last, "tool_calls") and last.tool_calls:
                        for tc in last.tool_calls:
                            tool_msg = SseMessage(
                                type="content",
                                data=f"\n🔧 调用工具: {tc['name']}...\n"
                            )
                            yield f"event: message\ndata: {json.dumps(tool_msg.model_dump(), ensure_ascii=False)}\n\n"

                    if content and not getattr(last, "tool_calls", None) and msg_type == "ai":
                        final_content = content

            if final_content:
                await session_store.store_tool_result(
                    f"aiops_report_{int(time.time())}", final_content, ttl=30 * 24 * 3600
                )
                sep = SseMessage(type="content", data="\n\n" + "=" * 60 + "\n")
                yield f"event: message\ndata: {json.dumps(sep.model_dump(), ensure_ascii=False)}\n\n"

                for i in range(0, len(final_content), 80):
                    chunk = final_content[i : i + 80]
                    msg = SseMessage(type="content", data=chunk)
                    yield f"event: message\ndata: {json.dumps(msg.model_dump(), ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.01)
            else:
                warn = SseMessage(type="content", data="⚠️ Agent 已完成，但未能生成最终报告。")
                yield f"event: message\ndata: {json.dumps(warn.model_dump(), ensure_ascii=False)}\n\n"

        except Exception as e:
            err = SseMessage(type="error", data=str(e))
            yield f"event: message\ndata: {json.dumps(err.model_dump(), ensure_ascii=False)}\n\n"

        done = SseMessage(type="done", data=None)
        yield f"event: message\ndata: {json.dumps(done.model_dump(), ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
