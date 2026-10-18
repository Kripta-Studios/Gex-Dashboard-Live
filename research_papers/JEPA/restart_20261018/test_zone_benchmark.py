"""Synthetic causal/accounting checks; no market data access."""
import importlib.util
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

spec=importlib.util.spec_from_file_location('zone_benchmark',Path(__file__).with_name('zone_benchmark.py'))
z=importlib.util.module_from_spec(spec)
spec.loader.exec_module(z)

def test_ib_ignores_current_future_and_invalid_samples():
    times=pd.date_range('2023-01-03 09:30',periods=100,freq='min')
    s=pd.Series(np.arange(100)+100.,index=times)
    s.iloc[0]=np.nan
    expected=z.ib_bounds(s,pd.Timestamp('2023-01-03 10:35'))
    s.loc['2023-01-03 10:30':]=1e10
    assert expected==(101.,159.)
    assert z.ib_bounds(s,pd.Timestamp('2023-01-03 10:35'))==expected
    assert z.ib_bounds(s,pd.Timestamp('2023-01-03 10:29')) is None
    s.iloc[:4]=np.nan
    assert z.ib_bounds(s,pd.Timestamp('2023-01-03 10:35')) is None

def test_contract_selection_no_late_quote_and_tie_strike():
    ts=pd.Timestamp('2023-01-03 10:34')
    f=pd.DataFrame({'timestamp':[ts,ts,ts+pd.Timedelta(minutes=1)],'right':['CALL']*3,
                    'strike':[101.,100.,99.],'delta':[.4,.4,.5],'bid':[1.]*3,'ask':[1.1]*3})
    assert z.contract_at(f,ts,'CALL').strike==100.
    f.loc[2,'delta']=.01
    assert z.contract_at(f,ts,'CALL').strike==100.

def test_same_contract_missing_entry_does_not_reselect():
    ts=pd.Timestamp('2023-01-03 10:36')
    candidates=[{'strike':100.,'right':'CALL','entry_time':ts,'exit_time':ts+pd.Timedelta(minutes=30),'event_id':'a'}]
    counts=Counter()
    rows=z.labels_for(candidates,{(101.,'CALL',ts):(1.,1.1)},counts)
    assert np.isnan(rows[0]['net'])
    assert counts['missing_entry']==1

def test_missing_exit_zero_and_accounting():
    ts=pd.Timestamp('2023-01-03 10:36')
    candidates=[{'strike':100.,'right':'CALL','entry_time':ts,'exit_time':ts+pd.Timedelta(minutes=30),'event_id':'a'}]
    counts=Counter()
    rows=z.labels_for(candidates,{(100.,'CALL',ts):(1.,1.1)},counts)
    assert rows[0]['missing_exit']
    assert rows[0]['net']==pytest.approx(-113.6)
    assert rows[0]['adverse_net']==pytest.approx(-114.6)
    assert z.payoff(1,1.2)==pytest.approx(15.4)

def test_no_overlap_next_decision_precedes_existing_exit():
    rows=[]
    for i,minute in enumerate((35,65,95)):
        d=pd.Timestamp('2023-01-03 10:00')+pd.Timedelta(minutes=minute)
        rows.append({'decision':str(d),'ticker_name':'SPY','right':'CALL','prediction':10.,'net':1.,
                     'exit_time':str(d+pd.Timedelta(minutes=31)),'event_id':str(i)})
    ledger=z.schedule(pd.DataFrame(rows),0)
    assert ledger.event_id.tolist()==['0','2']
    assert z.schedule(pd.DataFrame(rows),None).empty
    assert z.schedule(pd.DataFrame(rows),10).empty

def test_invalid_selected_entry_no_action_replacement():
    d=pd.Timestamp('2023-01-03 10:35')
    f=pd.DataFrame([{'decision':str(d),'ticker_name':'SPY','right':side,'prediction':pred,'net':net,
                      'exit_time':str(d+pd.Timedelta(minutes=31))} for side,pred,net in [('CALL',10,np.nan),('PUT',5,20)]])
    assert z.schedule(f,0).empty

def test_soft_zone_is_continuous_and_placebo_changes_location():
    a=z.soft_fields([100],[1],100,99,10,'x')
    b=z.soft_fields([100],[1],100.001,99,10,'x')
    p=z.soft_fields([103.7],[1],100,99,10,'x')
    assert abs(a['x_influence10']-b['x_influence10'])<1e-5
    assert p['x_influence10']<a['x_influence10']

def test_oi_future_report_not_visible():
    ts=pd.Timestamp('2023-01-03 10:34')
    oi=pd.DataFrame({'strike':[100.,100.],'right':['CALL','CALL'],
                     'timestamp':[ts-pd.Timedelta(minutes=1),ts+pd.Timedelta(minutes=1)],'open_interest':[10.,999.]})
    assert z.oi_snapshot(oi,ts).open_interest.iloc[0]==10.

def test_features_unaffected_by_future_spot_perturbation_and_expose_missingness():
    ts=pd.Timestamp('2023-01-03 10:34'); decision=ts+pd.Timedelta(minutes=1)
    s=pd.Series(np.arange(120)*.01+100.,index=pd.date_range('2023-01-03 09:30',periods=120,freq='min'))
    s.loc['2023-01-03 10:32']=np.nan
    chain=pd.DataFrame({'right':['CALL','PUT'],'strike':[100.,101.],'open_interest':[10.,20.],'gamma_density_proxy':[20.,40.]})
    a=z.features_for(s,chain,None,ts,decision,'SPY',z.ib_bounds(s,decision),{},0.)
    s.loc[ts+pd.Timedelta(minutes=1):]=1e9
    b=z.features_for(s,chain,None,ts,decision,'SPY',z.ib_bounds(s,decision),{},0.)
    for original,changed in zip(a,b):
        assert original.keys()==changed.keys()
        for key in original:
            assert original[key]==pytest.approx(changed[key],nan_ok=True)
    assert a[0]['candle5_observed_fraction']==.8
    assert a[0]['ib_observed_minutes']==60

def test_identity_normalization_before_duplicates_and_off_grid():
    day=pd.Timestamp('2023-01-03')
    f=pd.DataFrame({'symbol':['SPY']*3,'expiration':['2023-01-03']*3,'trade_date':['2023-01-03']*3,
                    'right':['C','CALL','PUT'],'strike':['100',100.,101.],
                    'timestamp':['2023-01-03T10:34:00','2023-01-03T10:34:00','2023-01-03T10:34:01']})
    counts=Counter(); z.clean_identity(f,'SPY',day,'greek',counts)
    assert f.empty
    assert counts['greek_duplicate_keys']==2
    assert counts['greek_invalid_identity']==1

def test_placebo_shift_is_reproducible_varied_and_not_feature():
    vals=[z.placebo_shift('SPY',f'202301{k:02d}') for k in range(1,31)]
    assert vals[0]==z.placebo_shift('SPY','20230101')
    assert all(.2<=abs(v)<=.8 for v in vals)
    assert len(set(vals))==30 and min(vals)<0<max(vals)
    assert z.placebo_shift('SPXW','20230101')!=vals[0]
