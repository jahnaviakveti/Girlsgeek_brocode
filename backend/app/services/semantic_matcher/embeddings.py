from abc import ABC, abstractmethod
from typing import List
import numpy as np

class EmbeddingModel(ABC):
    @abstractmethod
    def encode(self, texts: List[str]) -> np.ndarray:
        """Encode a list of strings into a NumPy array of embeddings."""
        pass
        
    @abstractmethod
    def encode_one(self, text: str) -> np.ndarray:
        """Encode a single string into a 1D NumPy array."""
        pass

class LocalSentenceTransformerEmbeddingModel(EmbeddingModel):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        
    def _get_model(self):
        if self._model is None:
            # Lazy loading to avoid overhead and early failures if not used
            from sentence_transformers import SentenceTransformer
            try:
                self._model = SentenceTransformer(self.model_name, local_files_only=True)
            except Exception:
                self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: List[str]) -> np.ndarray:
        if not texts:
            # Return empty array with correct shape if possible, but 0-dim is fine if empty
            return np.array([])
        model = self._get_model()
        return model.encode(texts, convert_to_numpy=True)

    def encode_one(self, text: str) -> np.ndarray:
        if not text:
            return np.array([])
        model = self._get_model()
        # encode returns a list/array of embeddings if given a list, or a single embedding if given a string
        return model.encode(text, convert_to_numpy=True)
