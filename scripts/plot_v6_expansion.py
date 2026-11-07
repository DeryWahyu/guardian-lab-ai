"""Plot paired aggregate expanded-data results without loading any URL data."""

import json

import numpy as np

from guardian_ml.paths import ROOT


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    report = json.loads(
        (ROOT / "ml/reports/v6-expanded-data-evaluation.json").read_text()
    )
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
    for row_index, (name, title) in enumerate(
        [
            ("new_domain_holdout", "New domain holdout from added sources"),
            ("observed_vendor", "Previously observed vendor benchmark"),
        ]
    ):
        models = report["cohorts"][name]["models"]
        for column, key in enumerate(("recall", "fpr")):
            ax = axes[row_index, column]
            values = (
                np.array(
                    [models[model]["warning"][key] for model in ("v6", "candidate")]
                )
                * 100
            )
            intervals = (
                np.array(
                    [
                        models[model]["warning"]["domain_bootstrap95"][key + "95"]
                        for model in ("v6", "candidate")
                    ]
                )
                * 100
            )
            ax.bar([0, 1], values, color=["#176b87", "#db8f38"])
            limit = (
                105 if key == "recall" else max(2, float(intervals[:, 1].max()) * 1.4)
            )
            for index, (value, interval) in enumerate(zip(values, intervals)):
                ax.plot([index, index], interval, color="black", linewidth=2)
                ax.text(
                    index, interval[1] + limit * 0.025, f"{value:.2f}%", ha="center"
                )
            ax.set(
                xticks=[0, 1],
                xticklabels=["Frozen v6", "Selected candidate"],
                ylabel="Percent",
                ylim=(0, limit),
                title=title
                + "\n"
                + ("Phishing recall" if key == "recall" else "False-positive rate"),
            )
    fig.suptitle(
        "Expanded-data Logistic Regression research experiment\nWarning policies fixed before scoring; 95% domain bootstrap intervals; publisher labels"
    )
    fig.savefig(ROOT / "ml/reports/v6-expanded-data-evaluation.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
