"""Deterministic URL byte tokens and a small padding-aware character CNN.

No trained checkpoint ships here. Dataset fitting requires the separate v10 data gate.
"""

import numpy as np
import torch
from torch import nn

from .preprocessing import prepare_url

PAD, UNKNOWN, CUT = 0, 1, 2
VOCAB_SIZE = 259


def tokenize(cores, max_length=512):
    if max_length < 8:
        raise ValueError("sequence_length_too_small")
    matrix = np.zeros((len(cores), max_length), dtype=np.int64)
    truncated = np.zeros(len(cores), dtype=bool)
    for i, core in enumerate(cores):
        if prepare_url(core).core != core:
            raise ValueError("canonical_core_required")
        raw = list(core.split("://", 1)[1].encode("utf-8"))
        values = [byte + 3 for byte in raw]
        if len(values) > max_length:
            head = 3 * max_length // 4
            values = values[:head] + [CUT] + values[-(max_length - head - 1) :]
            truncated[i] = True
        matrix[i, : len(values)] = values
    return torch.from_numpy(matrix), truncated


class CharacterCNN(nn.Module):
    def __init__(self, embedding=16, channels=32, kernels=(3, 5, 7), dropout=0.2):
        super().__init__()
        if any(k % 2 == 0 for k in kernels):
            raise ValueError("odd_convolution_kernels_required")
        self.embedding = nn.Embedding(VOCAB_SIZE, embedding, padding_idx=PAD)
        self.convolutions = nn.ModuleList(
            [nn.Conv1d(embedding, channels, k, padding=k // 2) for k in kernels]
        )
        self.head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(channels * len(kernels), 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
        )

    def forward(self, tokens):
        mask = tokens.ne(PAD).unsqueeze(1)
        if not mask.any(dim=2).all():
            raise ValueError("empty_token_sequence")
        embedded = self.embedding(tokens).transpose(1, 2)
        pooled = [
            torch.relu(layer(embedded)).masked_fill(~mask, -torch.inf).amax(dim=2)
            for layer in self.convolutions
        ]
        return self.head(torch.cat(pooled, dim=1)).squeeze(1)
