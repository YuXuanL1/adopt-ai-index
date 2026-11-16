"""Optional NLP cross-check for Part 1.5 (run with --nlp-check).

The sector tags themselves come from evidence (segments, SIC, recordkeeping test).
This module asks a second, independent question: "which sector definitions does this
firm's business description read most like?" If the NLP suggests a sector the evidence
didn't give, the firm is flagged for a person to look at.

  tfidf : TF-IDF vectors + cosine similarity (scikit-learn; runs anywhere)
  embed : sentence embeddings (sentence-transformers, all-MiniLM-L6-v2; ~90 MB download)
"""
from __future__ import annotations

import numpy as np

from text_utils import chunk_words


def similarity_scores(texts: dict[str, str], definitions: dict[str, str], method: str = "tfidf",
                      top_k: int = 10, model_name: str = "all-MiniLM-L6-v2") -> dict[str, dict[str, float]]:
    """{firm_id: {sector: score}}: mean similarity of a firm's 10 best-matching 200-word chunks."""
    sectors = list(definitions)
    chunks = {fid: chunk_words(t) for fid, t in texts.items() if t.strip()}
    if not chunks:
        return {}
    if method == "embed":
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise SystemExit("--nlp-method embed needs: pip install sentence-transformers") from e
        model = SentenceTransformer(model_name)
        def_vecs = model.encode([definitions[s] for s in sectors], normalize_embeddings=True)
        return {fid: _top_k_mean(model.encode(ch, normalize_embeddings=True) @ def_vecs.T, sectors, top_k)
                for fid, ch in chunks.items()}

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    all_chunks = [c for ch in chunks.values() for c in ch]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True, max_df=0.9,
                          token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9\(\)\-]+\b")
    vec.fit(all_chunks + [definitions[s] for s in sectors])
    def_mat = vec.transform([definitions[s] for s in sectors])
    return {fid: _top_k_mean(cosine_similarity(vec.transform(ch), def_mat), sectors, top_k)
            for fid, ch in chunks.items()}


def _top_k_mean(sims: np.ndarray, sectors: list[str], k: int) -> dict[str, float]:
    k = max(1, min(k, sims.shape[0]))
    return {s: float(v) for s, v in zip(sectors, np.sort(sims, axis=0)[-k:, :].mean(axis=0))}


def suggested(scores: dict[str, float], rel: float = 0.8, skip: frozenset = frozenset({"pension"})) -> set[str]:
    usable = {s: v for s, v in scores.items() if s not in skip}
    if not usable:
        return set()
    top = max(usable.values())
    return {s for s, v in usable.items() if v >= rel * top}
