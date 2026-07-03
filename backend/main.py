"""FastAPI 后端入口

运行方式:
    uvicorn backend.main:app --reload --port 8000

前端开发时 CORS 允许 localhost:5173 (Vite 默认端口)。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from backend.api import agent, chat, mistakes, books, kg, exercises, system, reports, assets, highlights, jobs

app = FastAPI(
    title="考研智能辅助系统 API",
    description="FastAPI + React 架构后端",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────
# 允许前端开发服务器跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite 默认
        "http://localhost:3000",   # React 默认
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API 路由 ──────────────────────────────────────────────
app.include_router(chat.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
app.include_router(mistakes.router, prefix="/api")
app.include_router(books.router, prefix="/api")
app.include_router(kg.router, prefix="/api")
app.include_router(exercises.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(assets.router, prefix="/api/system")
app.include_router(highlights.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")

# ── 健康检查 ──────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}

# ── 启动预热 ──────────────────────────────────────────────
@app.on_event("startup")
def _warmup():
    """启动时预热：加载嵌入模型和向量库，避免首请求长时间等待。"""
    import time
    t0 = time.time()
    try:
        from backend.job_manager import get_job_manager

        interrupted = get_job_manager().mark_running_interrupted()
        if interrupted:
            print(f"[jobs] marked {interrupted} unfinished jobs interrupted")
    except Exception as e:
        print(f"[jobs] startup recovery failed: {e}")
    if os.getenv('SKIP_EMBEDDING_WARMUP', '0') == '1':
        print('[warmup] embeddings skipped')
    else:
        try:
            from config import get_embeddings
            get_embeddings()
            print(f"[warmup] embeddings loaded in {time.time()-t0:.1f}s")
        except Exception as e:
            print(f"[warmup] embeddings failed: {e}")

    t1 = time.time()
    if os.getenv('SKIP_VECTOR_WARMUP', '0') == '1':
        print('[warmup] vector_store skipped')
    else:
        try:
            from ingestion.vector_store import get_vector_store
            get_vector_store()
            print(f'[warmup] vector_store loaded in {time.time()-t1:.1f}s')
        except Exception as e:
            print(f'[warmup] vector_store failed: {e}')

    print("[warmup] concept graph warmup skipped")

    print(f"[warmup] total {time.time()-t0:.1f}s")


# ── 静态文件（前端 build 产物）─────────────────────────────
# 如果 frontend/dist 存在，挂载为静态文件服务
_dist_path = Path(__file__).parent.parent / "frontend" / "dist"
if _dist_path.exists():
    app.mount("/", StaticFiles(directory=str(_dist_path), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
