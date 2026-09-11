"""
HIT140 Group 81 - Analytic Task 4: Shooting
Jobanpreet Singh

Research question:
Is the mean number of shots on target per 90 minutes (SoT/90) different
between teams that advanced beyond the group stage and teams eliminated in
the group stage at the 2026 FIFA World Cup?

This script completes the required work in Python:
1. data wrangling
2. data preparation and sampling
3. descriptive statistics
4. confidence intervals
5. a two-sample t-test
6. visualisation
"""

from pathlib import Path
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
RAW_FILE = HERE / "fbref_world_cup_2026_shooting_raw.csv"
SEED = 81  # Group 81; keeps the random sample reproducible
ALPHA = 0.05


# 1) DATA WRANGLING
raw = pd.read_csv(RAW_FILE)
print(f"Raw data: {raw.shape[0]} rows x {raw.shape[1]} columns")

# Rename the columns used in the analysis so the code is easier to follow.
df = raw.rename(
    columns={
        "# Pl": "Players",
        "90s": "Nineties",
        "Gls": "Goals",
        "Sh": "Shots",
        "SoT": "Shots_on_target",
        "SoT%": "Shots_on_target_pct",
        "Sh/90": "Shots_per90",
        "SoT/90": "SoT_per90",
        "G/Sh": "Goals_per_shot",
        "G/SoT": "Goals_per_SoT",
        "PK": "Penalty_goals",
        "PKatt": "Penalty_attempts",
    }
)

numeric_columns = [
    "Players", "Nineties", "Goals", "Shots", "Shots_on_target",
    "Shots_on_target_pct", "Shots_per90", "SoT_per90",
    "Goals_per_shot", "Goals_per_SoT", "Penalty_goals", "Penalty_attempts",
]

df["Squad"] = df["Squad"].astype(str).str.strip()
df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors="coerce")

df = df.drop_duplicates(subset="Squad")
df = df.dropna(subset=["Squad", "Nineties", "SoT_per90"])

if len(df) != 48:
    raise ValueError(f"Expected 48 teams after cleaning, found {len(df)}.")

print(f"Rows after cleaning: {len(df)}")
print(f"Missing SoT/90 after cleaning: {df['SoT_per90'].isna().sum()}")


# 2) DATA PREPARATION AND SAMPLING
# Each team played three group-stage matches. More than 3.0 '90s' means the
# team also played at least one knockout match. Extra time explains values
# such as 4.3 or 5.3 for some teams.
df["Progress"] = np.where(
    df["Nineties"] > 3.0,
    "Advanced",
    "Group-stage exit",
)

population_counts = df["Progress"].value_counts()
if population_counts.get("Advanced", 0) != 32:
    raise ValueError("Expected 32 advanced teams.")
if population_counts.get("Group-stage exit", 0) != 16:
    raise ValueError("Expected 16 group-stage exits.")

print("\nPopulation:")
print(population_counts.to_string())

# Population = all 48 World Cup teams.
# Sample = 36 teams. Stratified sampling keeps the population's 2:1 balance:
# 24 of 32 advanced teams and 12 of 16 group-stage exits.
advanced_sample = df[df["Progress"] == "Advanced"].sample(n=24, random_state=SEED)
exit_sample = df[df["Progress"] == "Group-stage exit"].sample(n=12, random_state=SEED)

sample = pd.concat([advanced_sample, exit_sample], ignore_index=True)
sample = sample.sort_values(["Progress", "Squad"]).reset_index(drop=True)
sample.to_csv(HERE / "joban_shooting_sample_seed81.csv", index=False)

print("\nStratified sample:")
print(sample["Progress"].value_counts().to_string())
print(f"Total sample size: {len(sample)}")


# 3) DESCRIPTIVE STATISTICS
summary = (
    sample.groupby("Progress")["SoT_per90"]
    .agg(n="count", mean="mean", sd="std", median="median", minimum="min", maximum="max")
    .reset_index()
)
summary.to_csv(HERE / "joban_descriptive_statistics.csv", index=False)

print("\nDescriptive statistics for SoT/90:")
print(summary.round(3).to_string(index=False))

advanced = sample.loc[sample["Progress"] == "Advanced", "SoT_per90"]
exited = sample.loc[sample["Progress"] == "Group-stage exit", "SoT_per90"]


# 4) 95% CONFIDENCE INTERVALS
def mean_ci(values, confidence=0.95):
    values = pd.Series(values).dropna().astype(float)
    n = len(values)
    mean = values.mean()
    standard_error = values.std(ddof=1) / math.sqrt(n)
    critical_value = stats.t.ppf((1 + confidence) / 2, df=n - 1)
    margin = critical_value * standard_error
    return mean, mean - margin, mean + margin


adv_mean, adv_low, adv_high = mean_ci(advanced)
exit_mean, exit_low, exit_high = mean_ci(exited)

# Welch confidence interval for the difference in means.
mean_difference = advanced.mean() - exited.mean()
variance_part_1 = advanced.var(ddof=1) / len(advanced)
variance_part_2 = exited.var(ddof=1) / len(exited)
difference_se = math.sqrt(variance_part_1 + variance_part_2)
welch_df = (variance_part_1 + variance_part_2) ** 2 / (
    (variance_part_1 ** 2) / (len(advanced) - 1)
    + (variance_part_2 ** 2) / (len(exited) - 1)
)
critical_difference = stats.t.ppf(0.975, df=welch_df)
diff_low = mean_difference - critical_difference * difference_se
diff_high = mean_difference + critical_difference * difference_se

confidence_intervals = pd.DataFrame(
    [
        ["Advanced mean SoT/90", adv_mean, adv_low, adv_high],
        ["Group-stage exit mean SoT/90", exit_mean, exit_low, exit_high],
        ["Difference (Advanced - Exit)", mean_difference, diff_low, diff_high],
    ],
    columns=["Estimate", "Value", "CI_95_Lower", "CI_95_Upper"],
)
confidence_intervals.to_csv(HERE / "joban_confidence_intervals.csv", index=False)

print("\n95% confidence intervals:")
print(confidence_intervals.round(3).to_string(index=False))


# 5) WELCH TWO-SAMPLE T-TEST
# H0: mean SoT/90 is equal in the two groups.
# H1: mean SoT/90 is different in the two groups.
# Welch's version is used because it does not assume equal variances.
test = stats.ttest_ind(advanced, exited, equal_var=False)

if test.pvalue < ALPHA:
    decision = "Reject H0"
    conclusion = (
        "There is evidence of a difference in mean SoT/90. "
        "The advanced teams have the higher sample mean."
    )
else:
    decision = "Fail to reject H0"
    conclusion = "There is not enough evidence of a difference in mean SoT/90."

print("\nWelch two-sample t-test:")
print("H0: the two population means are equal")
print("H1: the two population means are different")
print(f"t({welch_df:.2f}) = {test.statistic:.3f}")
print(f"p-value = {test.pvalue:.4f}")
print(f"Decision at alpha = {ALPHA}: {decision}")
print("Conclusion:", conclusion)

results = pd.DataFrame(
    {
        "Metric": [
            "Advanced sample mean SoT/90",
            "Group-stage exit sample mean SoT/90",
            "Mean difference (Advanced - Exit)",
            "Difference 95% CI lower",
            "Difference 95% CI upper",
            "Welch t statistic",
            "Welch degrees of freedom",
            "Two-sided p-value",
            "Decision (alpha=0.05)",
        ],
        "Value": [
            advanced.mean(),
            exited.mean(),
            mean_difference,
            diff_low,
            diff_high,
            test.statistic,
            welch_df,
            test.pvalue,
            decision,
        ],
    }
)
results.to_csv(HERE / "joban_test_results.csv", index=False)


# 6) VISUALISATIONS
# Simple plots are used because the assignment is about the analysis, not fancy slides.
fig, ax = plt.subplots(figsize=(7.4, 4.6))
ax.boxplot(
    [advanced.to_numpy(), exited.to_numpy()],
    tick_labels=["Advanced", "Group-stage exit"],
    showmeans=True,
)
ax.set_ylabel("Shots on target per 90 minutes")
ax.set_title("Shots on target per 90 in the stratified sample")
ax.grid(axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(HERE / "joban_sot90_boxplot.png", dpi=180, bbox_inches="tight")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.4, 3.8))
ax.errorbar(
    [mean_difference],
    [0],
    xerr=[[mean_difference - diff_low], [diff_high - mean_difference]],
    fmt="o",
    capsize=8,
)
ax.axvline(0, linewidth=1)
ax.set_yticks([0])
ax.set_yticklabels(["Advanced - Exit"])
ax.set_xlabel("Difference in mean SoT/90")
ax.set_title("95% confidence interval for the mean difference")
ax.grid(axis="x", alpha=0.25)
fig.tight_layout()
fig.savefig(HERE / "joban_difference_ci.png", dpi=180, bbox_inches="tight")
plt.close(fig)

print("\nOutput files saved in the project folder.")
