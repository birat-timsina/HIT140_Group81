"""Run after project.py: python test_project.py"""
import json
import unittest
import numpy as np
import pandas as pd
import project as p

class IntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m,cls.h=p.load_data()
        cls.d=p.build_features(cls.m,cls.h)

    def test_exact_shape_and_unique_matches(self):
        self.assertEqual(self.d.shape,(104,10))
        self.assertTrue(self.d.match_id.is_unique)
        self.assertEqual(list(self.d),['match_id']+p.FEATURES+[p.TARGET])

    def test_signed_target(self):
        np.testing.assert_array_equal(self.d[p.TARGET],self.m.goals_a-self.m.goals_b)

    def test_no_missing_or_infinite_values(self):
        self.assertTrue(np.isfinite(self.d[p.FEATURES+[p.TARGET]].to_numpy()).all())

    def test_competitive_history_and_cutoff(self):
        a=pd.read_csv(p.ROOT/'data/rolling_history_2080.csv')
        self.assertEqual(len(a),2080)
        self.assertTrue(a.competitive.all())
        self.assertTrue((a.date<a.prediction_date).all())
        self.assertTrue((a.groupby(['match_id','side']).size()==10).all())

    def test_nested_opponent_history_cutoff(self):
        a=pd.read_csv(p.ROOT/'data/opponent_history_20800.csv')
        self.assertEqual(len(a),20800)
        self.assertTrue((a.date<a.outer_history_date).all())
        self.assertTrue(a.competitive.all())

    def test_workload_date_interval(self):
        a=pd.read_csv(p.ROOT/'data/workload_history.csv')
        days=(pd.to_datetime(a.prediction_date)-pd.to_datetime(a.date)).dt.days
        self.assertTrue(days.between(1,30).all())

    def test_world_cup_experience_is_prior_tournaments(self):
        a=pd.read_csv(p.ROOT/'data/world_cup_experience_history.csv')
        self.assertTrue(a.date.str[:4].isin(['2014','2018','2022']).all())
        self.assertTrue((a.tournament=='FIFA World Cup').all())

    def test_first_row_direct_arithmetic(self):
        a=pd.read_csv(p.ROOT/'data/rolling_history_2080.csv',dtype={'match_id':str})
        a=a[a.match_id==self.m.match_id.iloc[0]]
        sides={k:v for k,v in a.groupby('side')}
        gap=sum(sides['a'].points)/10-sum(sides['b'].points)/10
        self.assertAlmostEqual(self.d.competitive_form_gap.iloc[0],gap)

    def test_future_results_do_not_change_earlier_inputs(self):
        cutoff=self.m.match_date.iloc[82]
        altered=self.h.copy()
        altered.loc[altered.date>=cutoff,['gf','ga','points']]=[20,10,3]
        after=p.build_features(self.m,altered)
        mask=self.m.match_date<=cutoff
        pd.testing.assert_frame_equal(self.d.loc[mask,p.FEATURES],after.loc[mask,p.FEATURES])

    def test_swapping_teams_negates_inputs_and_prediction(self):
        swapped=self.m.copy()
        swapped[['team_a','team_b']]=swapped[['team_b','team_a']].to_numpy()
        swapped[p.TARGET]=-swapped[p.TARGET]
        reverse=p.build_features(swapped,self.h)
        np.testing.assert_allclose(reverse[p.FEATURES],-self.d[p.FEATURES])
        fit=p.model().fit(self.d[p.FEATURES],self.d[p.TARGET])
        np.testing.assert_allclose(fit.predict(reverse[p.FEATURES]),-fit.predict(self.d[p.FEATURES]),atol=1e-12)

    def test_temporal_splits(self):
        tr,te,folds=p.splits(self.m)
        self.assertEqual((len(tr),len(te)),(82,22))
        self.assertLess(self.m.match_date.iloc[tr].max(),self.m.match_date.iloc[te].min())
        for a,b in folds:
            self.assertLess(self.m.match_date.iloc[a].max(),self.m.match_date.iloc[b].min())
            self.assertTrue((set(a)|set(b))<=set(tr))

    def test_equation_reproduces_predictions(self):
        e=json.loads((p.ROOT/'results/model_equation.json').read_text())
        q=pd.read_csv(p.ROOT/'results/later_match_predictions.csv',dtype={'match_id':str})
        x=self.d.set_index('match_id').loc[q.match_id,p.FEATURES].to_numpy()
        b=np.array([e['coefficients'][f] for f in p.FEATURES])
        np.testing.assert_allclose(x@b,q.prediction,atol=1e-9)

if __name__=='__main__':unittest.main(verbosity=2)
