import logging

from app.services.llm import get_client

logger = logging.getLogger(__name__)


async def generate_embedding(text: str):
    """
    Generate vector embedding for text using Mistral.
    Returns list[float], or None when the LLM is unavailable or the call fails.

    Note: mistral-embed returns 1024-dim vectors, while messages.embedding is
    declared as Vector(1536). Fix the column size before persisting these.
    """
    client = get_client()
    if client is None:
        return None

    try:
        response = await client.embeddings.create_async(
            model="mistral-embed",
            inputs=[text],
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None
