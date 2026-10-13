# Group 81 Objective 2.1

Owner: Birat Timsina. Revised project: competitive form and match context.

## Open these first

1. `deliverables/Objective_2_1_Report.docx` explains the question, every feature and the actual results.
2. `deliverables/Objective_2_1_Presentation.pptx` contains six main slides and two backup slides.
3. `WALKTHROUGH.ipynb` contains executed explanatory cells and saved outputs.
4. `data/model_dataset_104.csv` is the assignment model table: match_id + exactly eight inputs + goal_difference.
5. `PRESENTATION_SCRIPT.md` has a short speaking script and questions to practise.

## Reproduce the analysis

Extract this entire folder. In a terminal inside it:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python project.py
python test_project.py
python build_deliverables.py
```

`project.py` reads the preserved snapshots, rebuilds all CSVs, fits linear regression and creates charts. It needs no internet connection after dependencies are installed. `test_project.py` runs 12 integrity checks. `build_deliverables.py` refreshes the Word report and notebook. The presentation is editable; after changing numerical results, also update its values using `presentation/build_slides.mjs` with the documented artifact-tool runtime, or edit the deck directly. Ordinary analysis reproduction does not require the presentation-authoring runtime.

The notebook has saved outputs so you can read it before installing anything. Run it from this project folder to regenerate them. The environment actually used is in `results/environment.json`.

## Eight features

All are Team A minus Team B. Team order follows FIFA.

1. Competitive form: mean 3/1/0 result points over ten earlier competitive matches.
2. Clean sheets: fraction of those matches with no goals conceded.
3. Scoring failure: fraction with no goals scored.
4. Margin volatility: sample standard deviation of historical goal differences.
5. Form momentum: points per game in the latest five minus the preceding five.
6. Schedule strength: mean earlier points per game of the ten historical opponents, measured BEFORE each historical game.
7. Workload: number of earlier internationals during the preceding 30 days, including friendlies.
8. World Cup experience: log(1 + matches played in the 2014, 2018 and 2022 World Cups).

The competition list is explicit in `project.py` and `data/competition_definition.csv`. This means selected major competitions, not every event with 'Cup' in its name. For the first World Cup match we use earlier qualifying/continental/nations-league history. Later completed World Cup games enter the rolling window.

## Traceability

- `raw/`: exact original snapshots, URLs and hashes from the earlier acquisition.
- `data/official_matches.csv`: dates, teams, goals and separate shootout fields. The target includes extra time and excludes shootouts.
- `data/source_reconciliation.csv`: all 104 scores agree across the snapshots after resolving three reversed team orders.
- `data/rolling_history_2080.csv`: ten contributing matches for each of 208 team-match combinations.
- `data/opponent_history_20800.csv`: ten earlier matches behind each opponent-strength value.
- `data/workload_history.csv` and `world_cup_experience_history.csv`: the other contributing events.
- `data/team_components_208.csv`: component values before subtraction. Column names retain the model feature name, but values here are ONE team's component, not a gap.
- `results/`: metrics, predictions, feature removal checks, sensitivity, coefficients, correlations and test log.

## Interpretation and requirements

This version replaces the original raw scoring/conceding averages, rest and host variables with a different feature design. It remains a result-history model, not a shot-based xG model. Bayesian smoothing of goal counts by itself does not create observed shot-based xG.

The later 22 matches were already inspected in version 1. All current feature calculations respect time and training uses earlier matches, but this is a retrospective redesign, not a new untouched test. The additional sequential backtest is also retrospective.

No automatic feature search was performed to maximise the later-block score. The sensitivity variants remain diagnostic; the eight competitive features were retained. Both successful and unsuccessful checks of predictive usefulness are reported.

Before submission, settle the three points in `REQUIREMENTS_AND_OVERLAP.md`: the final 2.2 overlap count, permission for the historical external source, and the target score convention. This is not guaranteed compliance with unseen marking criteria. Review the code, use the real current assessment instructions, and complete the official AI declaration.
