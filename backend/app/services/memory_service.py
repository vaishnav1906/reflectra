from sqlalchemy import text

async def retrieve_memories(db, user_id, embedding, limit=5):
    if embedding is None:
        print("⚠️ Skipping memory retrieval (no embedding)")
        return []

    query = text("""
        SELECT content, similarity
        FROM match_messages(
            :query_embedding,
            0.75,
            :limit,
            :user_id
        )
    """)

    vector_string = "[" + ",".join(map(str, embedding)) + "]"

    result = await db.execute(
        query,
        {
            "query_embedding": vector_string,
            "limit": limit,
            "user_id": str(user_id)
        }
    )

    rows = result.fetchall()

    memories = list(dict.fromkeys(row[0] for row in rows))
    print("🧠 Retrieved memories:", memories)

    return memories