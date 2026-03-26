import os
from mistralai import Mistral
import logging

logger = logging.getLogger(__name__)

mistral_client = None

def get_client():
    global mistral_client
    if mistral_client is None:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY not found")
        mistral_client = Mistral(api_key=api_key)
    return mistral_client


async def generate_embedding(text: str):
    """
    Generate vector embedding for text using Mistral.
    Returns list[float]
    """

    try:
        client = get_client()

        response = client.embeddings.create(
            model="mistral-embed",
            inputs=[text]
        )

        embedding = response.data[0].embedding
        if embedding is None:
            print("⚠️ Embedding failed (rate limit)")
            return None
        return embedding

    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None