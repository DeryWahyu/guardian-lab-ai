"""Record evaluation start against an already frozen selection, then score once."""

from threadpoolctl import threadpool_limits

from guardian_ml.metadata import checksum
from experiment_v6_expanded_data import now, write_json
import experiment_v6_learning as study


def main():
    path = study.RUN / "evaluation-started.json"
    selected_hash = checksum(study.RUN / "selected-frozen.json")
    if path.exists():
        previous = study.read(path)
        if previous["selection_sha256"] != selected_hash:
            raise ValueError("learning_selection_changed_since_evaluation_start")
    else:
        write_json(
            path,
            {
                "started_at_utc": now(),
                "selection_sha256": selected_hash,
                "entrypoint_sha256": checksum(__file__),
            },
        )
    with threadpool_limits(limits=4):
        study.evaluate()


if __name__ == "__main__":
    main()
