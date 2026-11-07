"""Plot saved aggregate results with uncertainty and the small-benign warning."""

import argparse
import json
from pathlib import Path

import numpy as np

from guardian_ml.paths import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", type=Path, default=ROOT / "ml/reports/legitphish-v6-evaluation.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "ml/reports/legitphish-v6-evaluation.png"
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "ml/reports"):
        raise ValueError("plot_output_outside_report_directory")
    report = json.loads(args.report.read_text())
    rows = report["metrics"]
    if not report["binary_evaluation_performed"]:
        raise ValueError("no_two_class_results_to_plot")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    names = list(rows)
    for ax, key, title in [
        (axes[0], "recall", "Publisher-labelled phishing recall"),
        (axes[1], "fpr", "False-positive rate: only 28 benign"),
    ]:
        values = np.array([rows[name][key] for name in names]) * 100
        if key == "recall":
            intervals = (
                np.array(
                    [rows[name]["domain_bootstrap95"]["recall95"] for name in names]
                )
                * 100
            )
        else:
            intervals = (
                np.array(
                    [rows[name]["fpr_wilson95_rows_iid_assumption"] for name in names]
                )
                * 100
            )
        ax.bar(names, values, color=["#176b87", "#db8f38"])
        for index, (value, interval) in enumerate(zip(values, intervals)):
            ax.plot([index, index], interval, color="black", linewidth=2)
            ax.plot(
                [index - 0.07, index + 0.07], [interval[1], interval[1]], color="black"
            )
            ax.text(
                index,
                interval[1] + (2 if key == "recall" else 0.4),
                f"{value:.2f}%",
                ha="center",
            )
        ax.set(ylabel="Percent", title=title, ylim=(0, 100 if key == "recall" else 15))
    axes[0].set_xlabel("Frozen policy; bars are 95% domain-bootstrap intervals")
    axes[1].set_xlabel("95% Wilson intervals; zero-error bootstrap is uninformative")
    axes[1].text(
        0.5,
        0.7,
        "0 / 28 FP\nUpper Wilson bound: 12.06%\nDoes not establish FPR < 1%",
        transform=axes[1].transAxes,
        ha="center",
        fontsize=10,
    )
    fig.suptitle(
        "Frozen v6 on curated LegitPhish V2\n42,688 publisher-labelled phishing and 28 benign; global historical subset"
    )
    fig.savefig(output, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
