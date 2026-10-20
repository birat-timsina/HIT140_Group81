"""Group 81 Objective 2.1. Run: python project.py

from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import sklearn

ROOT = Path(__file__).resolve().parent
FEATURES = ['competitive_form_gap', 'clean_sheet_gap', 'scoring_failure_gap',
            'margin_volatility_gap', 'form_momentum_gap', 'schedule_strength_gap',
            'workload_30d_gap', 'world_cup_experience_gap']
LABELS = ['Competitive form', 'Clean sheets', 'Scoring failure', 'Margin volatility',
          'Form momentum', 'Past opponent strength', '30 day workload', 'World Cup experience']
TARGET = 'goal_difference'
ALIASES = {'Cabo Verde':'Cape Verde', 'Congo DR':'DR Congo', 'Czechia':'Czech Republic',
           "Côte d'Ivoire":'Ivory Coast', 'IR Iran':'Iran', 'Korea Republic':'South Korea',
           'Türkiye':'Turkey', 'USA':'United States'}
# An explicit operational definition, not every event described as a cup.
COMPETITIONS = {
    'FIFA World Cup', 'FIFA World Cup qualification',
    'UEFA Euro', 'UEFA Euro qualification', 'UEFA Nations League',
    'Copa América', 'Copa América qualification',
    'African Cup of Nations', 'African Cup of Nations qualification',
    'AFC Asian Cup', 'AFC Asian Cup qualification',
    'Gold Cup', 'Gold Cup qualification', 'CONCACAF Nations League',
    'CONCACAF Nations League qualification',
    'Oceania Nations Cup', 'Oceania Nations Cup qualification',
    'CONMEBOL–UEFA Cup of Champions',
}

def csv(frame, name, folder='results'):
    (ROOT/folder).mkdir(exist_ok=True)
    frame.to_csv(ROOT/folder/name, index=False, float_format='%.12g')

def load_data():
    official = json.loads((ROOT/'raw/fifa_matches.json').read_text())['Results']
    rows = []
    for m in official:
        names = [m[s]['TeamName'][0]['Description'] for s in ['Home','Away']]
        a,b = [ALIASES.get(n,n) for n in names]
        rows.append({'match_id':str(m['IdMatch']), 'match_date':m['LocalDate'][:10],
                     'kickoff_utc':m['Date'], 'team_a':a, 'team_b':b,
                     'goals_a':int(m['HomeTeamScore']), 'goals_b':int(m['AwayTeamScore']),
                     'shootout_a':m['HomeTeamPenaltyScore'], 'shootout_b':m['AwayTeamPenaltyScore'],
                     'stage':m['StageName'][0]['Description']})
    matches = pd.DataFrame(rows).sort_values(['kickoff_utc','match_id']).reset_index(drop=True)
    matches[TARGET] = matches.goals_a-matches.goals_b
    assert len(matches)==104 and matches.match_id.is_unique
    assert len(set(matches.team_a)|set(matches.team_b))==48
    h = pd.read_csv(ROOT/'raw/international_results.csv')
    assert not h.duplicated().any()
    wc = h[(h.tournament=='FIFA World Cup') & h.date.str.startswith('2026')]
    assert len(wc)==104
    reconciliation=[]
    for m in matches.itertuples():
        same=wc[(wc.date==m.match_date)&(wc.home_team==m.team_a)&(wc.away_team==m.team_b)]
        rev=wc[(wc.date==m.match_date)&(wc.home_team==m.team_b)&(wc.away_team==m.team_a)]
        assert len(same)+len(rev)==1
        row=rev.iloc[0] if len(rev) else same.iloc[0]
        scores=(row.away_score,row.home_score) if len(rev) else (row.home_score,row.away_score)
        assert scores==(m.goals_a,m.goals_b)
        reconciliation.append({'match_id':m.match_id,'history_order_reversed':bool(len(rev)), 'scores_agree':True})
    history=h[h.date < matches.match_date.min()].copy()
    history['history_id']=['history_csv_line_'+str(i+2) for i in history.index]
    history['source']='international_results'
    tour=pd.DataFrame({'date':matches.match_date, 'home_team':matches.team_a, 'away_team':matches.team_b,
                       'home_score':matches.goals_a,'away_score':matches.goals_b,
                       'tournament':'FIFA World Cup','history_id':matches.match_id,'source':'FIFA'})
    history=pd.concat([history,tour],ignore_index=True)
    assert history[['home_score','away_score']].notna().all().all()
    team_rows=[]
    for r in history.itertuples():
        for team,opponent,gf,ga in [(r.home_team,r.away_team,r.home_score,r.away_score),
                                   (r.away_team,r.home_team,r.away_score,r.home_score)]:
            team_rows.append({'history_id':r.history_id,'date':r.date,'team':team,'opponent':opponent,
                              'gf':int(gf),'ga':int(ga),'points':3 if gf>ga else 1 if gf==ga else 0,
                              'tournament':r.tournament,'competitive':r.tournament in COMPETITIONS,'source':r.source})
    long=pd.DataFrame(team_rows).sort_values(['date','history_id']).reset_index(drop=True)
    csv(matches,'official_matches.csv','data')
    csv(pd.DataFrame(reconciliation),'source_reconciliation.csv','data')
    csv(pd.DataFrame(ALIASES.items(),columns=['fifa_name','history_name']),'team_aliases.csv','data')
    csv(pd.DataFrame({'included_competition':sorted(COMPETITIONS)}),'competition_definition.csv','data')
    return matches,long

def build_features(matches, long, n=10, export=False, include_friendlies=False):
    """Auditable rolling competitive features, plus workload and historic experience."""
    grouped={team:g for team,g in long.groupby('team',sort=False)}
    opponent_cache={}
    rows=[]; components=[]; audit=[]; nested=[]; workload_audit=[]; experience_audit=[]
    for m in matches.itertuples():
        values={}
        for side,team in [('a',m.team_a),('b',m.team_b)]:
            all_prior=grouped[team][grouped[team].date<m.match_date]
            valid=all_prior if include_friendlies else all_prior[all_prior.competitive]
            recent=valid.tail(n)
            assert len(recent)==n and not recent.date.duplicated().any(), (team,m.match_date,n)
            # Schedule difficulty measured BEFORE each historical game, not after it.
            opponent_scores=[]
            for r in recent.itertuples():
                key=(r.opponent,r.date,n,include_friendlies)
                if key not in opponent_cache:
                    before=grouped[r.opponent]
                    before=before[before.date<r.date]
                    before=before if include_friendlies else before[before.competitive]
                    before=before.tail(n)
                    assert len(before)==n, ('opponent history incomplete',key,len(before))
                    opponent_cache[key]=before
                before=opponent_cache[key]
                opponent_scores.append(before.points.mean())
                if export:
                    audit.append({'match_id':m.match_id,'prediction_date':m.match_date,'side':side,
                                  **r._asdict(), 'opponent_prior_ppg':before.points.mean(),
                                  'opponent_history_latest':before.date.max()})
                    for s in before.to_dict('records'):
                        nested.append({'match_id':m.match_id,'side':side,'outer_history_id':r.history_id,
                                       'outer_history_date':r.date,**s})
            lower=(pd.Timestamp(m.match_date)-pd.Timedelta(days=30)).strftime('%Y-%m-%d')
            workload=all_prior[all_prior.date>=lower]  # includes friendlies: all team appearances
            # Last three completed tournaments, fixed before 2026. Team institution, not player caps.
            experience=all_prior[(all_prior.tournament=='FIFA World Cup') &
                                 all_prior.date.str[:4].isin(['2014','2018','2022'])]
            margins=recent.gf-recent.ga
            half=n//2
            v=[recent.points.mean(),(recent.ga==0).mean(),(recent.gf==0).mean(),
               margins.std(ddof=1),recent.points.iloc[-half:].mean()-recent.points.iloc[:-half].mean(),
               float(np.mean(opponent_scores)),len(workload),np.log1p(len(experience))]
            values[side]=np.array(v,dtype=float)
            if export:
                components.append({'match_id':m.match_id,'prediction_date':m.match_date,'team':team,'side':side,
                                   'first_history_date':recent.date.min(),'last_history_date':recent.date.max(),
                                   'history_n':n,'world_cup_matches_2014_2022':len(experience),
                                   **dict(zip(FEATURES,v))})
                for r in workload.to_dict('records'):
                    workload_audit.append({'match_id':m.match_id,'side':side,'prediction_date':m.match_date,**r})
                for r in experience.to_dict('records'):
                    experience_audit.append({'match_id':m.match_id,'side':side,**r})
        rows.append({'match_id':m.match_id,**dict(zip(FEATURES,values['a']-values['b'])),TARGET:m.goal_difference})
    frame=pd.DataFrame(rows)
    assert frame.shape==(104,10)
    assert np.isfinite(frame[FEATURES+[TARGET]].to_numpy()).all()
    if export:
        csv(frame,'model_dataset_104.csv','data')
        csv(pd.DataFrame(components),'team_components_208.csv','data')
        csv(pd.DataFrame(audit).drop(columns='Index'),'rolling_history_2080.csv','data')
        csv(pd.DataFrame(nested),'opponent_history_20800.csv','data')
        csv(pd.DataFrame(workload_audit),'workload_history.csv','data')
        csv(pd.DataFrame(experience_audit),'world_cup_experience_history.csv','data')
    return frame

def model(intercept=False):
    # No centering + no intercept guarantees f(-X) = -f(X).
    return make_pipeline(StandardScaler(with_mean=intercept),LinearRegression(fit_intercept=intercept))

def scores(y,p):
    return {'MAE':float(mean_absolute_error(y,p)), 'RMSE':float(np.sqrt(mean_squared_error(y,p))),
            'R2':float(r2_score(y,p))}

def splits(matches):
    # Retain the earlier version's date cutoff, to avoid searching for a nicer result.
    train=np.flatnonzero(matches.match_date<'2026-07-02')
    test=np.flatnonzero(matches.match_date>='2026-07-02')
    dates=sorted(matches.match_date.iloc[train].unique())
    # Half of training dates form a warm-up; two following date blocks validate.
    blocks=np.array_split(dates,4)
    folds=[]
    for i in [2,3]:
        tr=np.flatnonzero(matches.match_date.isin(np.concatenate(blocks[:i])))
        va=np.flatnonzero(matches.match_date.isin(blocks[i]))
        folds.append((tr,va))
    return train,test,folds

def cv_predictions(frame,cols,folds,intercept=False):
    all_y=[];all_p=[]; fold_rows=[]
    for i,(tr,va) in enumerate(folds,1):
        fit=model(intercept).fit(frame.loc[tr,cols],frame.loc[tr,TARGET])
        p=fit.predict(frame.loc[va,cols]);y=frame.loc[va,TARGET]
        all_y.extend(y);all_p.extend(p)
        fold_rows.append({'fold':i,'train_n':len(tr),'validation_n':len(va),**scores(y,p)})
    return scores(all_y,all_p),fold_rows

def evaluate(matches, frame, long):
    train,test,folds=splits(matches)
    X=frame[FEATURES];y=frame[TARGET]
    fit=model().fit(X.iloc[train],y.iloc[train])
    p=fit.predict(X.iloc[test]);pt=fit.predict(X.iloc[train])
    output=[{'model':'Eight feature OLS','split':'training',**scores(y.iloc[train],pt)},
            {'model':'Eight feature OLS','split':'later matches',**scores(y.iloc[test],p)},
            {'model':'Always zero','split':'later matches',**scores(y.iloc[test],np.zeros(len(test)))},
            {'model':'Training mean','split':'later matches',**scores(y.iloc[test],np.repeat(y.iloc[train].mean(),len(test)))}]
    csv(pd.DataFrame(output),'metrics.csv')
    cv,fold_rows=cv_predictions(frame,FEATURES,folds)
    csv(pd.DataFrame(fold_rows),'validation_metrics.csv')
    ab=[]
    for f,label in zip(FEATURES,LABELS):
        reduced,by_fold=cv_predictions(frame,[c for c in FEATURES if c!=f],folds)
        deltas=[b['MAE']-full['MAE'] for b,full in zip(by_fold,fold_rows)]
        ab.append({'feature':f,'label':label,'full_cv_MAE':cv['MAE'], 'removed_cv_MAE':reduced['MAE'],
                   'delta_MAE':reduced['MAE']-cv['MAE'],'fold_1_delta':deltas[0],'fold_2_delta':deltas[1]})
    csv(pd.DataFrame(ab),'feature_ablation.csv')
    sensitivity=[]
    for n in [6,10,14]:
        other=frame if n==10 else build_features(matches,long,n=n)
        v,_=cv_predictions(other,FEATURES,folds)
        sensitivity.append({'variant':f'{n} competitive matches','cv_MAE':v['MAE']})
    all_history=build_features(matches,long,include_friendlies=True)
    v,_=cv_predictions(all_history,FEATURES,folds)
    sensitivity.append({'variant':'10 internationals including friendlies','cv_MAE':v['MAE']})
    v,_=cv_predictions(frame,FEATURES,folds,intercept=True)
    sensitivity.append({'variant':'10 competitive matches with intercept','cv_MAE':v['MAE']})
    csv(pd.DataFrame(sensitivity),'sensitivity.csv')
    coefs=fit.named_steps['linearregression'].coef_/fit.named_steps['standardscaler'].scale_
    vif=[]
    for c in FEATURES:
        aux=LinearRegression().fit(X.iloc[train].drop(columns=c),X.iloc[train][c])
        r=aux.score(X.iloc[train].drop(columns=c),X.iloc[train][c])
        vif.append(float(1/(1-r)))
    csv(pd.DataFrame({'feature':FEATURES,'label':LABELS,'raw_coefficient':coefs,
                      'scaled_coefficient':fit.named_steps['linearregression'].coef_,'VIF':vif}),'coefficients.csv')
    predictions=matches.iloc[test].copy()
    predictions['prediction']=p;predictions['residual']=y.iloc[test].to_numpy()-p
    predictions['absolute_error']=abs(predictions.residual)
    csv(predictions,'later_match_predictions.csv')
    # Every match after the initial training window is predicted using earlier dates only.
    back=[]
    for date in sorted(matches.match_date.iloc[40:].unique()):
        tr=np.flatnonzero(matches.match_date<date);va=np.flatnonzero(matches.match_date==date)
        if len(tr)<40: continue
        f=model().fit(X.iloc[tr],y.iloc[tr]);pr=f.predict(X.iloc[va])
        for idx,pred in zip(va,pr):
            back.append({'match_id':matches.iloc[idx].match_id,'match_date':date,'train_n':len(tr),
                         'actual':int(y.iloc[idx]),'prediction':float(pred),'zero_prediction':0})
    back=pd.DataFrame(back);csv(back,'sequential_backtest.csv')
    csv(pd.DataFrame([{'model':'Expanding OLS',**scores(back.actual,back.prediction)},
                      {'model':'Always zero',**scores(back.actual,back.zero_prediction)}]),'sequential_metrics.csv')
    csv(frame[FEATURES+[TARGET]].describe().T.rename_axis('variable').reset_index(),'descriptive_statistics.csv')
    csv(matches.assign(split=np.where(matches.match_date<'2026-07-02','training','later matches')),
        'split_membership.csv','data')
    csv(pd.DataFrame([{'fold':i+1,'train_end':matches.match_date.iloc[t].max(),
                      'validation_start':matches.match_date.iloc[v].min(),
                      'validation_end':matches.match_date.iloc[v].max()} for i,(t,v) in enumerate(folds)]),'fold_dates.csv')
    corr=X.iloc[train].corr();corr.to_csv(ROOT/'results/training_correlations.csv')
    assert np.allclose(fit.predict(-X.iloc[test]),-p)
    equation={'features':FEATURES,'intercept':0,'coefficients':dict(zip(FEATURES,map(float,coefs))),
              'training_n':len(train),'evaluation_n':len(test)}
    (ROOT/'results/model_equation.json').write_text(json.dumps(equation,indent=2))
    summary={'matches':104,'features':8,'train_n':len(train),'later_n':len(test),
             'cv':cv,'later':scores(y.iloc[test],p),'zero_baseline':scores(y.iloc[test],np.zeros(len(test))),
             'sequential_n':len(back),'sequential':scores(back.actual,back.prediction),
             'sequential_zero':scores(back.actual,back.zero_prediction),
             'evaluation_status':'Retrospective redesign; final dates were seen in version 1',
             'overlap_status':'Audited: 0 exact overlaps; 2 related concepts in 2.2 candidate 8, 1 related in selected 4'}
    (ROOT/'results/summary.json').write_text(json.dumps(summary,indent=2))
    draw(pd.DataFrame(output),pd.DataFrame(ab),predictions,corr)
    print(json.dumps(summary,indent=2))
    return summary

def draw(metrics,ab,pred,corr):
    (ROOT/'charts').mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(8,4.5));m=metrics[metrics.split=='later matches']
    bars=ax.barh(m.model,m.MAE,color=['#146B78','#8D9AA1','#B5C1C5'])
    ax.bar_label(bars,fmt='%.3f',padding=5);ax.set_xlim(0,m.MAE.max()*1.2)
    ax.invert_yaxis();ax.set(xlabel='Mean absolute error in goals',title='Later 22 matches: lower error is better')
    fig.tight_layout();fig.savefig(ROOT/'charts/baselines.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5));a=ab.sort_values('delta_MAE')
    ax.barh(a.label,a.delta_MAE,color=['#146B78' if n>0 else '#BA6631' for n in a.delta_MAE])
    ax.axvline(0,color='black',lw=.8);ax.set(xlabel='Change in validation MAE after removal',title='Positive values suggest incremental usefulness')
    fig.tight_layout();fig.savefig(ROOT/'charts/ablation.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4.5));axes[0].scatter(pred.goal_difference,pred.prediction,color='#146B78')
    lo=min(pred.goal_difference.min(),pred.prediction.min())-.3;hi=max(pred.goal_difference.max(),pred.prediction.max())+.3
    axes[0].plot([lo,hi],[lo,hi],'--',color='grey');axes[0].set(xlabel='Actual goal difference',ylabel='Predicted goal difference',title='Later match predictions')
    axes[1].scatter(pred.prediction,pred.residual,color='#146B78');axes[1].axhline(0,color='grey',ls='--')
    axes[1].set(xlabel='Predicted goal difference',ylabel='Actual minus predicted',title='Residual pattern')
    fig.tight_layout();fig.savefig(ROOT/'charts/diagnostics.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,7));im=ax.imshow(corr,vmin=-1,vmax=1,cmap='RdBu_r')
    ax.set_xticks(range(8),LABELS,rotation=45,ha='right');ax.set_yticks(range(8),LABELS)
    for i in range(8):
        for j in range(8): ax.text(j,i,f'{corr.iloc[i,j]:.2f}',ha='center',va='center',color='white' if abs(corr.iloc[i,j])>.65 else 'black',fontsize=9)
    fig.colorbar(im,ax=ax,shrink=.7);ax.set_title('Training feature correlations')
    fig.tight_layout();fig.savefig(ROOT/'charts/correlations.png',dpi=170);plt.close(fig)

def main():
    for folder in ['data','results','charts']: (ROOT/folder).mkdir(exist_ok=True)
    m,h=load_data();d=build_features(m,h,export=True);evaluate(m,d,h)
    versions={'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,
              'scikit_learn':sklearn.__version__,'matplotlib':matplotlib.__version__}
    (ROOT/'results/environment.json').write_text(json.dumps(versions,indent=2))

if __name__=='__main__':main()
