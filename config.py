import os
import re
import base64
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv(os.getenv("ENV_PATH") or None)

# ===== Proxy configuration (VPN / mirror support) =====
_http_proxy = os.getenv("HTTP_PROXY", "")
_https_proxy = os.getenv("HTTPS_PROXY", "")
if _http_proxy:
    os.environ["HTTP_PROXY"] = _http_proxy
    os.environ["http_proxy"] = _http_proxy
if _https_proxy:
    os.environ["HTTPS_PROXY"] = _https_proxy
    os.environ["https_proxy"] = _https_proxy
    os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
    os.environ["no_proxy"] = "localhost,127.0.0.1,::1"

# HuggingFace mirror / proxy
if os.getenv("HF_PROXY"):
    os.environ["HTTP_PROXY"] = os.getenv("HF_PROXY")
    os.environ["HTTPS_PROXY"] = os.getenv("HF_PROXY")
    os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"

# Default to the mirror unless the user has configured HF_ENDPOINT.
if not os.getenv("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

BASE_DIR = Path(__file__).parent


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


DATA_DIR = _resolve_path(os.getenv("DATA_DIR", "./data"))


def _data_path(env_name: str, default_name: str) -> Path:
    raw = os.getenv(env_name)
    if raw:
        return _resolve_path(raw)
    return DATA_DIR / default_name


# LLM configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "deepseek-v4-pro")

# Kimi / Moonshot configuration
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", OPENAI_API_KEY)
MOONSHOT_API_BASE = os.getenv("MOONSHOT_API_BASE", "https://api.moonshot.cn/v1")

# DeepSeek V4 Pro configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", OPENAI_API_KEY)
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-v4-pro")

# Embedding model
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-zh-v1.5")
if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", EMBEDDING_MODEL_NAME or ""):
    EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"

# Data paths
VECTOR_DB_PATH = _data_path("VECTOR_DB_PATH", "vector_db")
BOOKS_PATH = _data_path("BOOKS_PATH", "books")
CHAPTERS_PATH = _data_path("CHAPTERS_PATH", "chapters")
PROGRESS_PATH = _data_path("PROGRESS_PATH", "progress")
IMAGES_PATH = _data_path("IMAGES_PATH", "images")
MINERU_OUTPUT_PATH = _resolve_path(os.getenv("MINERU_OUTPUT_PATH", "./mineru_output"))
MINERU_API_URL = os.getenv("MINERU_API_URL", "").rstrip("/")
MINERU_CLI_COMMAND = os.getenv("MINERU_CLI_COMMAND", "")
MINERU_TASK_TIMEOUT_SECONDS = int(os.getenv("MINERU_TASK_TIMEOUT_SECONDS", "3600"))
MINERU_TASK_POLL_SECONDS = float(os.getenv("MINERU_TASK_POLL_SECONDS", "2"))

# LLM backend. The default is DeepSeek.
LLM_BACKEND = os.getenv("LLM_BACKEND", "deepseek")

# Multimodal entrypoint is intentionally disabled unless OCR/Vision workflows enable it.
MULTIMODAL_ENABLED = False


def _get_chat_model(model: str, temperature: float, api_key: str, base_url: str, extra_body: Optional[dict] = None):
    from langchain_openai import ChatOpenAI

    kwargs = dict(
        model=model,
        temperature=temperature,
        api_key=api_key,
        base_url=base_url,
        streaming=True,
        timeout=120,
    )
    if "http_socket_options" in getattr(ChatOpenAI, "model_fields", {}):
        # Disable LangChain's custom socket transport so httpx can honor system proxies.
        kwargs["http_socket_options"] = ()
    if extra_body:
        kwargs["extra_body"] = extra_body
    return ChatOpenAI(**kwargs)


def get_llm(temperature=1):
    if LLM_BACKEND == "deepseek":
        return _get_chat_model(
            DEEPSEEK_MODEL_NAME,
            temperature,
            DEEPSEEK_API_KEY,
            DEEPSEEK_API_BASE,
            extra_body={"reasoning_effort": "high", "thinking": {"type": "enabled"}},
        )
    elif LLM_BACKEND == "moonshot":
        return _get_chat_model(LLM_MODEL_NAME, temperature, MOONSHOT_API_KEY, MOONSHOT_API_BASE)
    elif LLM_BACKEND == "openai":
        return _get_chat_model(LLM_MODEL_NAME, temperature, OPENAI_API_KEY, OPENAI_API_BASE)
    else:
        from langchain_community.chat_models import ChatOllama
        return ChatOllama(
            model=LLM_MODEL_NAME,
            temperature=temperature,
            base_url=OLLAMA_BASE_URL,
        )


def get_llm_client():
    """Return a non-streaming OpenAI-compatible client for utility calls."""
    from openai import OpenAI
    import httpx
    if LLM_BACKEND == "deepseek":
        return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_API_BASE, http_client=httpx.Client(trust_env=False, timeout=120))
    elif LLM_BACKEND == "moonshot":
        return OpenAI(api_key=MOONSHOT_API_KEY, base_url=MOONSHOT_API_BASE, http_client=httpx.Client(trust_env=False, timeout=120))
    elif LLM_BACKEND == "openai":
        return OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE, http_client=httpx.Client(trust_env=False, timeout=120))
    else:
        return None


def encode_image(image_path: str | Path) -> str:
    """Encode an image file as a base64 data URL payload."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# Embedding adapter used by Chroma.
_embeddings_instance = None


def get_embeddings():
    global _embeddings_instance
    if _embeddings_instance is not None:
        return _embeddings_instance
    print("  [embedding] loading model...", flush=True)

    import torch
    torch.set_num_threads(2)
    embedding_local_files_only = os.getenv("EMBEDDING_LOCAL_FILES_ONLY", "1") == "1"
    if embedding_local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
    # Text embeddings do not need torchvision. Some desktop/dev environments
    # contain a mismatched optional torchvision wheel that crashes during
    # transformers feature detection, so hide only that optional package while
    # importing the text stack.
    import importlib.util
    original_find_spec = importlib.util.find_spec
    importlib.util.find_spec = lambda name, *args, **kwargs: (
        None if name == "torchvision" or name.startswith("torchvision.")
        else original_find_spec(name, *args, **kwargs)
    )
    try:
        import transformers.utils.import_utils as transformers_import_utils
        transformers_import_utils._torchvision_available = False
    except Exception:
        pass

    try:
        from sentence_transformers import SentenceTransformer
    finally:
        importlib.util.find_spec = original_find_spec

    # Prefer the desktop/local snapshot so offline installs do not contact the Hub.
    _local_snapshot = DATA_DIR / "models" / "models--BAAI--bge-small-zh-v1.5" / "snapshots"
    _model_path = None
    if _local_snapshot.exists():
        _snapshots = list(_local_snapshot.iterdir())
        if _snapshots:
            _model_path = str(_snapshots[0])
            print(f"  [embedding] using local snapshot: {_model_path}", flush=True)

    _model = SentenceTransformer(
        _model_path or EMBEDDING_MODEL_NAME,
        device="cpu",
        cache_folder=str(DATA_DIR / "models"),
        local_files_only=embedding_local_files_only,
    )

    class _Embeddings:
        """Small Chroma-compatible wrapper exposing embed_documents / embed_query."""
        def embed_documents(self, texts):
            embs = _model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return embs.tolist()

        def embed_query(self, text):
            emb = _model.encode(text, normalize_embeddings=True, show_progress_bar=False)
            return emb.tolist()

    _embeddings_instance = _Embeddings()
    print("  [embedding] model ready", flush=True)
    return _embeddings_instance
