from sentence_transformers import SentenceTransformer


class EmbeddingGenerator:

    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def generate_embedding(self, text):

        return self.model.encode(
            text,
            normalize_embeddings=True
        )

    def generate_embeddings(self, chunks):

        texts = [chunk["text"] for chunk in chunks]

        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=True
        )

        results = []

        for chunk, embedding in zip(chunks, embeddings):

            results.append({
                "embedding": embedding,
                "text": chunk["text"],
                "metadata": chunk["metadata"]
            })

        return results