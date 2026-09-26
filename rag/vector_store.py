import faiss
import numpy as np


class VectorStore:

    def __init__(self, dimension):
        self.dimension = dimension

        self.index = faiss.IndexFlatIP(dimension)

        self.documents = []

    def add_embeddings(self, embeddings): # ye embeddings output lega

        vectors = np.array( # embeddings ko numpy array me convert kar raha hai taki vo faiss index me add ho sake
            [item["embedding"] for item in embeddings],
            dtype="float32"
        )

        self.index.add(vectors) # Faiss m add krega

        for item in embeddings:

            self.documents.append({
                "text": item["text"],
                "metadata": item["metadata"]
            })  # har vector ke corresponding metadata and text ko documents list me append kar raha hai taki baad me search karte waqt use kiya ja sake

    def search(self, query_embedding, k=3):

        query_vector = np.array(
         [query_embedding],
         dtype="float32"
    )

        scores, indices = self.index.search(
        query_vector,
        k
    )
        results = []

        for score, index in zip(scores[0], indices[0]):

           results.append({
            "text": self.documents[index]["text"],
            "metadata": self.documents[index]["metadata"],
            "score": float(score)
        })

        return results