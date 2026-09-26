class HybridRetriever:

    def __init__(self, vector_store, bm25_retriever):

        self.vector_store = vector_store
        self.bm25_retriever = bm25_retriever

    def search(self, query, query_embedding, k=3):

        # -------------------------
        # FAISS Search
        # -------------------------

        faiss_results = self.vector_store.search(
            query_embedding,
            k=10
        )

        # -------------------------
        # BM25 Search
        # -------------------------

        bm25_results = self.bm25_retriever.search(
            query,
            k=10
        )

        print("\n===== FAISS RESULTS =====")

        for result in faiss_results:
            print(
        result["metadata"].get("name"),
        result["metadata"].get("file")
    )

        print("\n===== BM25 RESULTS =====")

        for result in bm25_results:
            print(
        result["metadata"].get("name"),
        result["metadata"].get("file")
    )

        # -------------------------
        # Reciprocal Rank Fusion     # RRF is a method to combine the results from multiple search algorithms (in this case, FAISS and BM25) into a single ranked list.
        #  It assigns scores to each result based on its rank in the individual search results, and then combines these scores to produce a final ranking.
        # -------------------------

        rrf_scores = {}

        result_map = {}

        rank_constant = 60

        # FAISS results
        for rank, result in enumerate(faiss_results):
            meta = result["metadata"]
            key = f"{meta['file']}_{meta.get('name', '')}_{meta.get('start_line', 0)}"

            rrf_scores[key] = rrf_scores.get(key, 0) + (
                1 / (rank_constant + rank + 1)
            )

            result_map[key] = result

        # BM25 results
        for rank, result in enumerate(bm25_results):
            meta = result["metadata"]
            key = f"{meta['file']}_{meta.get('name', '')}_{meta.get('start_line', 0)}"

            rrf_scores[key] = rrf_scores.get(key, 0) + (
                1 / (rank_constant + rank + 1)
            )

            result_map[key] = result

        # -------------------------
        # Sort by RRF score
        # -------------------------

        ranked_keys = sorted( # highest to lowest sort
            rrf_scores,
            key=rrf_scores.get,
            reverse=True
        )
        #ranked_keys =
    #[
        #"rag_engine.py_49",
         #"rag_engine.py_22",
    #]
        # -------------------------
        # Final results
        # -------------------------

        final_results = []

        for key in ranked_keys[:k]:

            result = result_map[key].copy() # result_map ko result m dal dena

            result["rrf_score"] = rrf_scores[key] # rrf score ko result m add krna

            final_results.append(result)

        # TEMPORARY DEBUG
        print("\n===== RRF RESULTS BEFORE RERANKER =====")

        for result in final_results:
            print("----------------")
            print("RRF Score:", result["rrf_score"])
            print("Type:", result["metadata"].get("type"))
            print("Name:", result["metadata"].get("name"))


        return final_results

        