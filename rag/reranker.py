from sentence_transformers import CrossEncoder


class Reranker:

    def __init__(self):

        self.model = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )

    def rerank(self, query, results, k=3): # isko 3 things milte hai user query , rrf results of top k chunks,final k

        pairs = []

        for result in results:

            pairs.append(
                [
                    query,
                    result["text"]
                ]
            ) # pair m hog aise kuch ["user query","chunk text"] , ["user query","chunk text"] , ["user query","chunk text"]  and so on
        #"Where are embeddings generated?",
        #"def build_vector_store(...): ..."
    
        scores = self.model.predict(pairs) # predict scores for each pair, indicating how relevant each chunk is to the query. Ye har pair ka score calculate karega ki kitna relevant hai user query ke liye

        reranked_results = []

        for result, score in zip(results, scores):

            result = result.copy()

            result["rerank_score"] = float(score) # ab rerank score add kar diya har result m

            reranked_results.append(result) #fir isko append krdia

        reranked_results.sort(
            key=lambda x: x["rerank_score"], #rerank_score ko dekho aur highest score ko pehle rakho.
            reverse=True
        )

        return reranked_results[:k] # return top k results after reranking

    #RRF decide karta hai "dono retrievers ki rankings mila kar kaun upar hai",
    #  while Reranker actual query + chunk ko dekhkar decide karta hai "in candidates me se kaunsa chunk query ke liye sabse relevant hai."