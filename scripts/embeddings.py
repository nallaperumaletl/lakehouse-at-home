"""
Embedding Generator Service
============================
Provides text embedding generation using sentence-transformers.
Supports batch processing for efficiency.

Models available:
- all-MiniLM-L6-v2: Fast, 384 dimensions (default)
- all-mpnet-base-v2: Higher quality, 768 dimensions
- paraphrase-multilingual-MiniLM-L12-v2: Multilingual, 384 dimensions

Usage:
    from embeddings import EmbeddingGenerator

    gen = EmbeddingGenerator()
    embeddings = gen.encode(["hello world", "goodbye world"])
"""

import os
from typing import List, Union
import numpy as np

# Lazy loading to avoid import overhead when not needed
_model = None
_model_name = None


class EmbeddingGenerator:
    """Text embedding generator using sentence-transformers."""

    # Available models and their dimensions
    MODELS = {
        "all-MiniLM-L6-v2": 384,
        "all-mpnet-base-v2": 768,
        "paraphrase-multilingual-MiniLM-L12-v2": 384,
    }

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(self, model_name: str = None, device: str = None):
        """
        Initialize the embedding generator.

        Args:
            model_name: Name of the sentence-transformers model
            device: Device to use ('cpu', 'cuda', or None for auto)
        """
        self.model_name = model_name or os.environ.get(
            "EMBEDDING_MODEL", self.DEFAULT_MODEL
        )
        self.device = device or os.environ.get("EMBEDDING_DEVICE", None)
        self._model = None

    @property
    def dimension(self) -> int:
        """Get the embedding dimension for the current model."""
        return self.MODELS.get(self.model_name, 384)

    def _load_model(self):
        """Lazy load the model on first use."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                print(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name, device=self.device)
                print(f"Model loaded (dimension: {self.dimension})")
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Run: pip install sentence-transformers"
                )
        return self._model

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        show_progress: bool = False,
        normalize: bool = True,
    ) -> np.ndarray:
        """
        Generate embeddings for text(s).

        Args:
            texts: Single text string or list of texts
            batch_size: Batch size for encoding
            show_progress: Show progress bar
            normalize: Normalize embeddings to unit length

        Returns:
            numpy array of shape (n_texts, dimension)
        """
        model = self._load_model()

        if isinstance(texts, str):
            texts = [texts]

        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=normalize,
        )

        return embeddings

    def encode_single(self, text: str, normalize: bool = True) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text
            normalize: Normalize embedding to unit length

        Returns:
            List of floats (embedding vector)
        """
        embedding = self.encode([text], normalize=normalize)
        return embedding[0].tolist()


class MockEmbeddingGenerator:
    """
    Mock embedding generator for testing without loading real models.
    Generates deterministic pseudo-embeddings based on text hash.
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.model_name = "mock"

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        show_progress: bool = False,
        normalize: bool = True,
    ) -> np.ndarray:
        """Generate mock embeddings."""
        if isinstance(texts, str):
            texts = [texts]

        embeddings = []
        for text in texts:
            np.random.seed(hash(text) % (2**32))
            vec = np.random.randn(self.dimension).astype(np.float32)
            if normalize:
                vec = vec / np.linalg.norm(vec)
            embeddings.append(vec)

        return np.array(embeddings)

    def encode_single(self, text: str, normalize: bool = True) -> List[float]:
        """Generate mock embedding for single text."""
        return self.encode([text], normalize=normalize)[0].tolist()


def get_embedding_generator(use_mock: bool = False, **kwargs) -> EmbeddingGenerator:
    """
    Factory function to get an embedding generator.

    Args:
        use_mock: Use mock generator (for testing)
        **kwargs: Arguments passed to EmbeddingGenerator

    Returns:
        EmbeddingGenerator or MockEmbeddingGenerator instance
    """
    if use_mock or os.environ.get("USE_MOCK_EMBEDDINGS", "").lower() == "true":
        return MockEmbeddingGenerator(kwargs.get("dimension", 384))
    return EmbeddingGenerator(**kwargs)


# Module-level convenience functions
_default_generator = None


def encode(texts: Union[str, List[str]], **kwargs) -> np.ndarray:
    """Encode texts using the default generator."""
    global _default_generator
    if _default_generator is None:
        _default_generator = get_embedding_generator()
    return _default_generator.encode(texts, **kwargs)


def encode_single(text: str, **kwargs) -> List[float]:
    """Encode a single text using the default generator."""
    global _default_generator
    if _default_generator is None:
        _default_generator = get_embedding_generator()
    return _default_generator.encode_single(text, **kwargs)


if __name__ == "__main__":
    # Quick test
    print("Testing EmbeddingGenerator...")

    # Test mock generator
    mock_gen = MockEmbeddingGenerator()
    mock_embeddings = mock_gen.encode(["hello world", "goodbye world"])
    print(f"Mock embeddings shape: {mock_embeddings.shape}")
    print(f"Mock embedding sample: {mock_embeddings[0][:5]}...")

    # Test real generator if available
    try:
        gen = EmbeddingGenerator()
        embeddings = gen.encode(["hello world", "goodbye world"])
        print(f"Real embeddings shape: {embeddings.shape}")
        print(f"Real embedding sample: {embeddings[0][:5]}...")

        # Test similarity
        from numpy.linalg import norm

        similarity = np.dot(embeddings[0], embeddings[1])
        print(f"Similarity between texts: {similarity:.4f}")
    except ImportError as e:
        print(f"Real generator not available: {e}")

    print("Done!")
