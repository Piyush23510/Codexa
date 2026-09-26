from rank_bm25 import BM25Okapi


class BM25Retriever:

    def __init__(self, documents):

        self.documents = documents

        tokenized_documents = [ # convert each document's text to lowercase and split it into list of tokens (words) for BM25 processing
            document["text"].lower().split()
            for document in documents
        ]

        self.bm25 = BM25Okapi(tokenized_documents) #BM25 internally calculate karta hai ki Kaunsa word kis document me kitna important hai?

#For example query:

#Where are embeddings generated?

#BM25 "embeddings" aur "generated" jaise words ko dekhega aur calculate karega ki kaunse chunks me ye words useful way me appear ho rahe hain.

    def search(self, query, k=5):

        query_tokens = query.lower().split() # convert the query to lowercase and split it into list of tokens (words) for BM25 processing

        scores = self.bm25.get_scores(query_tokens) #Ye har document/chunk ka BM25 score calculate karega.

        ranked_indices = scores.argsort()[::-1][:k] # isse sabse bada score phele ajata hai aur usme se top k select kr lete hai

        results = []

        for index in ranked_indices:

            results.append({
                "text": self.documents[index]["text"],
                "metadata": self.documents[index]["metadata"],
                "bm25_score": float(scores[index])
            })

        return results