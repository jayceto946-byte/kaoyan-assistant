import os
import base64
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# LLM 配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "kimi-k2.6")

# Kimi K2.6 专属配置
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", OPENAI_API_KEY)
MOONSHOT_API_BASE = os.getenv("MOONSHOT_API_BASE", "https://api.moonshot.cn/v1")

# 嵌入模型
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-zh-v1.5")

# 路径
VECTOR_DB_PATH = BASE_DIR / os.getenv("VECTOR_DB_PATH", "./data/vector_db")
BOOKS_PATH = BASE_DIR / os.getenv("BOOKS_PATH", "./data/books")
CHAPTERS_PATH = BASE_DIR / os.getenv("CHAPTERS_PATH", "./data/chapters")
PROGRESS_PATH = BASE_DIR / "./data/progress"
IMAGES_PATH = BASE_DIR / os.getenv("IMAGES_PATH", "./data/images")

# 使用哪个LLM后端
LLM_BACKEND = os.getenv("LLM_BACKEND", "")
if not LLM_BACKEND:
    if MOONSHOT_API_KEY:
        LLM_BACKEND = "moonshot"
    elif OPENAI_API_KEY:
        LLM_BACKEND = "openai"
    else:
        LLM_BACKEND = "ollama"

# 是否支持多模态
MULTIMODAL_ENABLED = LLM_BACKEND in ("moonshot",)


def _get_chat_model(model: str, temperature: float, api_key: str, base_url: str):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=api_key,
        base_url=base_url,
    )


def get_llm(temperature=0.1):
    if LLM_BACKEND == "moonshot":
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
    """获取原始 OpenAI 客户端（用于多模态）"""
    from openai import OpenAI
    if LLM_BACKEND == "moonshot":
        return OpenAI(api_key=MOONSHOT_API_KEY, base_url=MOONSHOT_API_BASE)
    elif LLM_BACKEND == "openai":
        return OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)
    else:
        return None


def encode_image(image_path: str | Path) -> str:
    """将图片编码为 base64 data URL"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_embeddings():
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        model_kwargs = {"device": "cpu"}
        return HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            model_kwargs=model_kwargs,
            encode_kwargs={"normalize_embeddings": True},
        )
    except ImportError:
        from langchain_community.embeddings import HuggingFaceBgeEmbeddings
        model_kwargs = {"device": "cpu"}
        encode_kwargs = {"normalize_embeddings": True}
        return HuggingFaceBgeEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs,
        )
