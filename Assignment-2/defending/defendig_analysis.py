"""Complete the descriptive and inferential statistical analysis.

Run after 02_prepare_data.py:
    python 03_analysis.py
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import scipy.stats as st


ALPHA = 0.05
MEASURE = "direct_pressures_per90"
GROUP = "position"

PROJECT_FOLDER = Path(__file__).resolve().parent
DATA_FOLDER = PROJECT_FOLDER / "data"
RESULTS_FOLDER = PROJECT_FOLDER / "results"
CHARTS_FOLDER = PROJECT_FOLDER / "charts"


def descriptive_statistics(group_values: pd.Series) -> dict:
    """Return the descriptive statistics required for one group."""
    return {
        "n": group_values.count(),
        "mean": group_values.mean(),
        "median": group_values.median(),
        "standard_deviation": group_values.std(ddof=1),
        "variance": group_values.var(ddof=1),
        "minimum": group_values.min(),
        "q1": group_values.quantile(0.25),
        "q3": group_values.quantile(0.75),
        "maximum": group_values.max(),
        "iqr": group_values.quantile(0.75) - group_values.quantile(0.25),
    }


def mean_confidence_interval(
    group_values: pd.Series, confidence: float = 0.95
) -> dict:
    """Calculate a two-sided z confidence interval as taught in ci_mean.py."""
    non_missing_values = group_values.dropna()
    n = len(non_missing_values)

    # These steps follow the lecturer's ci_mean.py example.
    sample_mean = st.tmean(non_missing_values)
    sample_std = st.tstd(non_missing_values)
    z_score = st.norm.ppf(q=1 - (1 - confidence) / 2)
    standard_error = sample_std / math.sqrt(n)
    margin_of_error = z_score * standard_error

    return {
        "n": n,
        "mean": sample_mean,
        "standard_deviation": sample_std,
        "z_statistic": z_score,
        "standard_error": standard_error,
        "margin_of_error": margin_of_error,
        "confidence_level": confidence,
        "lower_bound": sample_mean - margin_of_error,
        "upper_bound": sample_mean + margin_of_error,
    }


def welch_difference_confidence_interval(
    defender_values: pd.Series,
    midfielder_values: pd.Series,
    confidence: float = 0.95,
) -> dict:
    """Calculate a Welch interval for defender mean minus midfielder mean."""
    defender_values = defender_values.dropna()
    midfielder_values = midfielder_values.dropna()

    defender_count = len(defender_values)
    midfielder_count = len(midfielder_values)
    defender_variance = defender_values.var(ddof=1)
    midfielder_variance = midfielder_values.var(ddof=1)
    defender_variance_component = defender_variance / defender_count
    midfielder_variance_component = midfielder_variance / midfielder_count
    standard_error = np.sqrt(
        defender_variance_component + midfielder_variance_component
    )
    degrees_freedom = (
        defender_variance_component + midfielder_variance_component
    ) ** 2 / (
        (defender_variance_component**2 / (defender_count - 1))
        + (midfielder_variance_component**2 / (midfielder_count - 1))
    )
    difference = defender_values.mean() - midfielder_values.mean()
    critical_value = st.t.ppf((1 + confidence) / 2, df=degrees_freedom)
    margin = critical_value * standard_error

    return {
        "comparison": "Defender minus Midfielder",
        "mean_difference": difference,
        "standard_error": standard_error,
        "degrees_freedom": degrees_freedom,
        "confidence_level": confidence,
        "lower_bound": difference - margin,
        "upper_bound": difference + margin,
    }


def save_boxplot(analysis_sample: pd.DataFrame) -> None:
    plt.figure(figsize=(9, 6))
    sns.boxplot(
        data=analysis_sample,
        x=GROUP,
        y=MEASURE,
        order=["Defender", "Midfielder"],
        hue=GROUP,
        palette=["#1f77b4", "#ff7f0e"],
        legend=False,
    )
    sns.stripplot(
        data=analysis_sample,
        x=GROUP,
        y=MEASURE,
        order=["Defender", "Midfielder"],
        color="black",
        alpha=0.45,
        jitter=0.18,
        size=4,
    )
    plt.title("Direct defensive pressures per 90 minutes")
    plt.xlabel("FIFA player position")
    plt.ylabel("Direct defensive pressures per 90")
    plt.tight_layout()
    plt.savefig(CHARTS_FOLDER / "01_boxplot_sample_distribution.png", dpi=200)
    plt.close()


def save_histogram(analysis_sample: pd.DataFrame) -> None:
    plt.figure(figsize=(9, 6))
    sns.histplot(
        data=analysis_sample,
        x=MEASURE,
        hue=GROUP,
        hue_order=["Defender", "Midfielder"],
        bins=12,
        kde=True,
        element="step",
        stat="density",
        common_norm=False,
        palette=["#1f77b4", "#ff7f0e"],
    )
    plt.title("Distribution of direct defensive pressure rates")
    plt.xlabel("Direct defensive pressures per 90")
    plt.ylabel("Density")
    plt.tight_layout()
    plt.savefig(CHARTS_FOLDER / "02_histogram_sample_distribution.png", dpi=200)
    plt.close()


def save_mean_chart(confidence_intervals: pd.DataFrame) -> None:
    ordered = confidence_intervals.set_index("position").loc[["Defender", "Midfielder"]]
    errors = np.vstack(
        [
            ordered["mean"] - ordered["lower_bound"],
            ordered["upper_bound"] - ordered["mean"],
        ]
    )

    plt.figure(figsize=(8, 6))
    plt.bar(
        ordered.index,
        ordered["mean"],
        yerr=errors,
        capsize=8,
        color=["#1f77b4", "#ff7f0e"],
        alpha=0.85,
    )
    plt.title("Sample means with 95% confidence intervals")
    plt.xlabel("FIFA player position")
    plt.ylabel("Mean direct defensive pressures per 90")
    plt.tight_layout()
    plt.savefig(CHARTS_FOLDER / "03_mean_95ci.png", dpi=200)
    plt.close()


def main() -> None:
    sample_file = DATA_FOLDER / "analysis_sample.csv"
    if not sample_file.exists():
        raise FileNotFoundError("Run 02_prepare_data.py before this file.")

    RESULTS_FOLDER.mkdir(parents=True, exist_ok=True)
    CHARTS_FOLDER.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")

    print("Step 1: Loading the stratified random sample...")
    analysis_sample = pd.read_csv(sample_file)

    # Keep the two position groups separate for all inferential calculations.
    defender_values = analysis_sample.loc[
        analysis_sample[GROUP] == "Defender", MEASURE
    ].dropna()
    midfielder_values = analysis_sample.loc[
        analysis_sample[GROUP] == "Midfielder", MEASURE
    ].dropna()

    print("Step 2: Calculating descriptive statistics...")
    descriptive_rows = []
    for position in ["Defender", "Midfielder"]:
        position_values = analysis_sample.loc[
            analysis_sample[GROUP] == position, MEASURE
        ]
        descriptive_rows.append(
            {"position": position, **descriptive_statistics(position_values)}
        )

    descriptive = pd.DataFrame(descriptive_rows)
    descriptive.to_csv(RESULTS_FOLDER / "descriptive_statistics.csv", index=False)

    print("Step 3: Calculating 95% confidence intervals for the means...")
    confidence_rows = []
    for position in ["Defender", "Midfielder"]:
        position_values = analysis_sample.loc[
            analysis_sample[GROUP] == position, MEASURE
        ]
        confidence_rows.append(
            {"position": position, **mean_confidence_interval(position_values)}
        )

    confidence_intervals = pd.DataFrame(confidence_rows)
    confidence_intervals.to_csv(
        RESULTS_FOLDER / "mean_confidence_intervals.csv", index=False
    )

    difference_interval = welch_difference_confidence_interval(
        defender_values, midfielder_values
    )
    pd.DataFrame([difference_interval]).to_csv(
        RESULTS_FOLDER / "mean_difference_confidence_interval.csv", index=False
    )

    print("Step 4: Running Welch's independent two-sample t-test...")

    # Calculate the same six summary values used in two-sample-t-test.py.
    defender_mean = st.tmean(defender_values)
    defender_std = st.tstd(defender_values)
    defender_count = len(defender_values)

    midfielder_mean = st.tmean(midfielder_values)
    midfielder_std = st.tstd(midfielder_values)
    midfielder_count = len(midfielder_values)

    # H0: mu_defenders = mu_midfielders
    # H1: mu_defenders != mu_midfielders (two-sided)
    t_statistic, p_value = st.ttest_ind_from_stats(
        defender_mean,
        defender_std,
        defender_count,
        midfielder_mean,
        midfielder_std,
        midfielder_count,
        equal_var=False,
        alternative="two-sided",
    )
    reject_null = bool(p_value < ALPHA)

    print("Step 5: Checking the sample distributions and variance difference...")
    defender_shapiro = st.shapiro(defender_values)
    midfielder_shapiro = st.shapiro(midfielder_values)
    levene_result = st.levene(
        defender_values, midfielder_values, center="median"
    )

    mean_difference = difference_interval["mean_difference"]

    # Interpret the test result together with the direction of the difference.
    if reject_null and mean_difference < 0:
        decision = "Reject H0"
        conclusion = (
            "The sample provides statistically significant evidence that "
            "midfielders have a higher mean direct defensive pressure rate than "
            "defenders."
        )
    elif reject_null and mean_difference > 0:
        decision = "Reject H0"
        conclusion = (
            "The sample provides statistically significant evidence that "
            "defenders have a higher mean direct defensive pressure rate than "
            "midfielders."
        )
    else:
        decision = "Fail to reject H0"
        conclusion = (
            "The sample does not provide statistically significant evidence that "
            "the mean direct defensive pressure rate differs between defenders "
            "and midfielders."
        )

    test_text = f"""Research question
Among FIFA World Cup 2026 players who played at least 180 minutes, was the mean
number of direct defensive pressures per 90 minutes different between defenders
and midfielders?

Hypotheses
H0: mu_defenders = mu_midfielders
H1: mu_defenders != mu_midfielders

Test
Welch independent two-sample t-test, two-sided, alpha = {ALPHA}

Results
Defender sample size: {len(defender_values)}
Midfielder sample size: {len(midfielder_values)}
Defender mean: {defender_values.mean():.3f}
Midfielder mean: {midfielder_values.mean():.3f}
Mean difference (Defender - Midfielder): {difference_interval['mean_difference']:.3f}
t statistic: {t_statistic:.4f}
Welch degrees of freedom: {difference_interval['degrees_freedom']:.2f}
p value: {p_value:.6f}
95% CI for mean difference: [{difference_interval['lower_bound']:.3f}, {difference_interval['upper_bound']:.3f}]
Decision: {decision}
Conclusion: {conclusion}

Supporting assumption checks
Shapiro-Wilk p value, defenders: {defender_shapiro.pvalue:.6f}
Shapiro-Wilk p value, midfielders: {midfielder_shapiro.pvalue:.6f}
Levene median-centred p value: {levene_result.pvalue:.6f}

Notes
- Welch's test does not require equal population variances.
- The defender sample is right-skewed. The balanced samples of 60 players per
  group make the t procedure reasonably robust through the central limit theorem.
- The test describes an association with player position; it does not prove
  that a position causes a particular pressure rate.
"""
    (RESULTS_FOLDER / "t_test_results.txt").write_text(test_text, encoding="utf-8")

    print("Step 6: Creating Python visualisations...")
    save_boxplot(analysis_sample)
    save_histogram(analysis_sample)
    save_mean_chart(confidence_intervals)

    summary_text = f"""# Initial analysis summary

## Research question

Among FIFA World Cup 2026 players who played at least 180 minutes, was the mean
number of direct defensive pressures per 90 minutes different between defenders
and midfielders?

## Main sample results

- Defenders: n = {len(defender_values)}, mean = {defender_values.mean():.2f}, SD = {defender_values.std(ddof=1):.2f}
- Midfielders: n = {len(midfielder_values)}, mean = {midfielder_values.mean():.2f}, SD = {midfielder_values.std(ddof=1):.2f}
- Difference (Defender - Midfielder) = {difference_interval['mean_difference']:.2f}
- Welch t = {t_statistic:.3f}, p = {p_value:.4f}
- 95% CI for the mean difference = [{difference_interval['lower_bound']:.2f}, {difference_interval['upper_bound']:.2f}]
- Statistical decision: {decision}

## Plain-language interpretation

{conclusion}
"""
    (RESULTS_FOLDER / "analysis_summary.md").write_text(
        summary_text, encoding="utf-8"
    )

    print("\nAnalysis complete.")
    print(test_text)
    print(f"Results saved in: {RESULTS_FOLDER}")
    print(f"Charts saved in: {CHARTS_FOLDER}")


if __name__ == "__main__":
    main()
