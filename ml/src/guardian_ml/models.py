"""Common prediction adapter; fitted transformations never see holdouts."""

from dataclasses import dataclass
import numpy as np
from scipy.sparse import csr_matrix, hstack
from .features import NUMERIC, CATEGORICAL, heuristic_scores


@dataclass
class Candidate:
    name: str
    kind: str
    estimator: object = None
    transformer: object = None

    def predict(self, cores, features, batch_size=4096):
        outputs = []
        for start in range(0, len(cores), batch_size):
            stop = start + batch_size
            part = features.iloc[start:stop]
            if self.kind == "heuristic":
                score = heuristic_scores(part)
            elif self.kind == "linear":
                matrix = self.transformer.transform(cores.iloc[start:stop])
                score = self.estimator.predict_proba(matrix)[:, 1]
            elif self.kind == "catboost":
                score = self.estimator.predict_proba(part, thread_count=4)[:, 1]
            else:
                score = self.estimator.predict_proba(self.xgb_matrix(part))[:, 1]
            outputs.append(score)
        return np.concatenate(outputs) if outputs else np.array([])

    def xgb_matrix(self, frame):
        return hstack(
            [
                csr_matrix(frame[list(NUMERIC)].to_numpy(dtype=np.float32)),
                self.transformer.transform(frame[list(CATEGORICAL)]),
            ],
            format="csr",
            dtype=np.float32,
        )
