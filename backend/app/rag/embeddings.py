from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
from fastembed import TextEmbedding


@dataclass
class FastEmbedder:
    """Lightweight embedding wrapper for MVP.

    Uses FastEmbed (ONNX Runtime under the hood). Good for Windows + Python 3.13.
    """
    model_name: str

    def __post_init__(self) -> None:
        self._model = TextEmbedding(model_name=self.model_name)

    @property
    def dim(self) -> int:
        v = next(self._model.embed(["dim probe"]))
        return int(len(v))

    def embed(self, texts: List[str]) -> List[List[float]]:
        vecs = list(self._model.embed(texts))
        return [np.asarray(v, dtype=np.float32).tolist() for v in vecs]

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]
