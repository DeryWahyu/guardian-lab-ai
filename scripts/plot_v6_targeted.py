"""Export aggregate experiment results without reading URL-level data."""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from guardian_ml.paths import ROOT


def main():
    path = ROOT / "ml/reports/v6-targeted-evaluation.json"
    report = json.loads(path.read_text())
    selected = report["selected_freeze"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 10), constrained_layout=True)
    fig.suptitle(
        "V6 research: source ablations and predeclared policies\nPublisher labels; historical data; no Indonesia gold or production approval",
        fontsize=14,
    )
    names = list(selected["tune"])
    values = [
        100 * selected["tune"][name]["strict_source_1pct"]["macro_source_recall"]
        for name in names
    ]
    colors = [
        "#087f8c" if name == selected["selection"]["candidate"] else "#8ab8ba"
        for name in names
    ]
    ax = axes[0, 0]
    ax.barh(names, values, color=colors)
    for i, value in enumerate(values):
        ax.text(value + 0.5, i, f"{value:.1f}%", va="center")
    ax.set(
        xlim=(0, max(values) * 1.25),
        xlabel="Macro source recall on common tune (%)",
        title="Fitting sources, same LR recipe and strict policy",
    )
    for ax, key, title in [
        (
            axes[0, 1],
            "new_pwd_domain_holdout",
            "PWD2021: new domains, historical source",
        ),
        (
            axes[1, 0],
            "observed_vendor",
            "Vendor: previously observed regression benchmark",
        ),
    ]:
        cohort = report["cohorts"][key]
        for model, color, marker in [
            ("v6", "#cf6a4c", "o"),
            ("candidate", "#087f8c", "s"),
        ]:
            names = [
                name
                for name in cohort["policies"]
                if name.startswith(model + "_pooled_")
            ]
            x = [100 * cohort["policies"][name]["fpr"] for name in names]
            y = [100 * cohort["policies"][name]["recall"] for name in names]
            ax.plot(
                x, y, marker=marker, color=color, label=model + ": fixed pooled budgets"
            )
            for name, vx, vy in zip(names, x, y):
                ax.annotate(
                    f"{100 * float(name.split('_pooled_')[1]):g}% dev",
                    (vx, vy),
                    xytext=(4, 4 if model == "v6" else -12),
                    textcoords="offset points",
                    fontsize=8,
                )
        for name, color, label in [
            ("v6_original", "#cf6a4c", "Original v6 warning"),
            ("candidate_strict_source_1pct", "#087f8c", "Candidate strict 1%/source"),
        ]:
            row = cohort["policies"][name]
            ax.scatter(
                [100 * row["fpr"]],
                [100 * row["recall"]],
                marker="*",
                s=150,
                color=color,
                label=label,
                zorder=5,
            )
        ax.set(
            xlabel="Observed false positive rate (%)",
            ylabel="Observed phishing recall (%)",
            title=title,
        )
        ax.grid(alpha=0.2)
        ax.legend(fontsize=7)
    ax = axes[1, 1]
    keys = [
        "new_pwd_domain_holdout",
        "observed_expanded_domain_holdout",
        "observed_vendor",
        "observed_phishtank_positive",
        "observed_legitphish",
    ]
    labels = [
        "PWD new",
        "Expanded seen",
        "Vendor seen",
        "PhishTank seen",
        "LegitPhish seen",
    ]
    x = np.arange(len(keys))
    for offset, name, color, label in [
        (-0.18, "v6_original", "#cf6a4c", "Original v6 warning"),
        (0.18, "candidate_strict_source_1pct", "#087f8c", "Selected candidate strict"),
    ]:
        values, lows, highs = [], [], []
        for key in keys:
            row = report["cohorts"][key]["policies"][name]
            value = row["recall"]
            low, high = row["domain_bootstrap95"]["recall95"]
            values.append(100 * value)
            lows.append(max(0, 100 * (value - low)))
            highs.append(max(0, 100 * (high - value)))
        ax.bar(
            x + offset,
            values,
            width=0.36,
            yerr=[lows, highs],
            capsize=2,
            color=color,
            label=label,
        )
    ax.set(
        xticks=x,
        xticklabels=labels,
        ylabel="Phishing recall (%)",
        title="Original vs selected strict policy; domain 95% intervals",
        ylim=(0, 100),
    )
    ax.tick_params(axis="x", rotation=20)
    ax.legend(fontsize=8)
    fig.savefig(path.with_suffix(".png"), dpi=160)
    plt.close(fig)
    print("Saved aggregate chart: " + str(path.with_suffix(".png")))


if __name__ == "__main__":
    main()
