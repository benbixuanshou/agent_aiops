import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

from app.models.schemas import ChatRequest, ApiResponse, ChatResponse, SseMessage
from app.session.manager import session_store

router = APIRouter()


@router.post("/chat")
async def chat(request: Request, req: ChatRequest):
    if not req.Question or not req.Question.strip():
        return JSONResponse(
            content=ApiResponse(code=400, message="Question cannot be empty").model_dump()
        )

    session = await session_store.get_or_create(req.Id)
    history = await session.get_history()

    supervisor = request.app.state.supervisor
    answer = await supervisor.invoke(req.Question)

    await session.add_message(req.Question, answer or "")
    await _maybe_compress(session, request.app.state.supervisor)
    return ApiResponse(data=ChatResponse(success=True, answer=answer or ""))


@router.post("/chat_stream")
async def chat_stream(request: Request, req: ChatRequest):
    if not req.Question or not req.Question.strip():
        return StreamingResponse(
            _error_stream("Question cannot be empty"),
            media_type="text/event-stream",
        )

    session = await session_store.get_or_create(req.Id)
    history = await session.get_history()

    supervisor = request.app.state.supervisor

    async def event_stream():
        full_answer = ""
        async for event in supervisor.astream(req.Question):
            msgs = event.get("messages", [])
            if msgs:
                last = msgs[-1]
                content = getattr(last, "content", "") or ""
                if hasattr(last, "tool_calls") and last.tool_calls:
                    for tc in last.tool_calls:
                        tool_msg = SseMessage(
                            type="content",
                            data=f"\n🔧 调用工具: {tc.get('name', 'unknown')}...\n"
                        )
                        yield f"event: message\ndata: {json.dumps(tool_msg.model_dump(), ensure_ascii=False)}\n\n"
                elif content:
                    full_answer += content
                    msg = SseMessage(type="content", data=content)
                    yield f"event: message\ndata: {json.dumps(msg.model_dump(), ensure_ascii=False)}\n\n"

        await session.add_message(req.Question, full_answer)
        await _maybe_compress(session, request.app.state.supervisor)

        done = SseMessage(type="done", data=None).model_dump()
        yield f"event: message\ndata: {json.dumps(done, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _maybe_compress(session, supervisor):
    """Check if session needs compression and run it."""
    if session.message_pair_count() > 6:
        async def summarize(prompt):
            from langchain_core.messages import HumanMessage
            r = await supervisor.llm.ainvoke([HumanMessage(content=prompt)])
            return r.content or ""
        await session.compress_history(summarize)


async def _error_stream(message: str):
    err = SseMessage(type="error", data=message).model_dump()
    yield f"event: message\ndata: {json.dumps(err, ensure_ascii=False)}\n\n"
