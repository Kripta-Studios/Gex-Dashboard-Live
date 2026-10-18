"""Fixed exploratory causal zone benchmark; see BENCHMARK_SPEC.md."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import pickle
import platform
import shutil
import time

for _thread_env in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_thread_env]='1'

import lightgbm as lgb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path('D:/ThetaData/data_options')
OUT = Path('D:/GexResearchArtifacts/restart_20261018/zone_benchmark_parallel_v3')
TICKERS = ('SPXW', 'SPY', 'QQQ')
RATIOS = np.array([-1,-.618,-.272,0,.236,.382,.5,.618,.786,1,1.272,1.618,2])
SEED = 20261018
GREEK_COLS = ['symbol','expiration','trade_date','strike','right','timestamp',
              'underlying_timestamp','underlying_price','delta','bid','ask',
              'implied_vol','vega','theta']
OI_COLS = ['symbol','expiration','trade_date','strike','right','timestamp','open_interest']

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8*1024*1024), b''): h.update(block)
    return h.hexdigest()

def placebo_shift(ticker,date):
    digest=hashlib.sha256(f'{SEED}|{ticker}|{date}'.encode()).digest()
    magnitude=.2+.6*int.from_bytes(digest[1:9],'big')/(2**64-1)
    return magnitude if digest[0]%2==0 else -magnitude

def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False, default=str), encoding='utf-8')

def parse_time(v):
    result=pd.to_datetime(v, format='ISO8601', errors='coerce')
    if result.dt.tz is not None: raise ValueError('Expected naive America/New_York source clocks')
    return result

def valid_quote(df):
    return (np.isfinite(df.bid) & np.isfinite(df.ask) & (df.bid>=0) & (df.ask>0) & (df.bid<=df.ask))

def ib_bounds(spot, decision):
    day = pd.Timestamp(decision).normalize()
    if pd.Timestamp(decision)<day+pd.Timedelta(hours=10,minutes=30): return None
    s = spot.loc[(spot.index>=day+pd.Timedelta(hours=9,minutes=30)) &
                 (spot.index<day+pd.Timedelta(hours=10,minutes=30)) &
                 (spot.index<pd.Timestamp(decision))].dropna()
    if len(s)<57: return None
    lo, hi = float(s.min()), float(s.max())
    return (lo,hi) if hi>lo else None

def contract_at(frame, stamp, right):
    f=frame.loc[(frame.timestamp==stamp)&(frame.right==right)&valid_quote(frame)&
                np.isfinite(frame.delta)&(frame.delta.abs()<=1)].copy()
    if f.empty: return None
    f['dist']=(f.delta.abs()-.5).abs()
    return f.sort_values(['dist','strike'],kind='stable').iloc[0]

def payoff(entry, exit_bid, slip=.01):
    return (max(float(exit_bid)-slip,0.)-float(entry)-slip)*100-2*1.30

def labels_for(candidates, quotes, counters):
    rows=[]
    for c in candidates:
        key=(c['strike'],c['right'],pd.Timestamp(c['entry_time']))
        ent=quotes.get(key)
        if ent is None:
            counters['missing_entry']+=1
            rows.append({'event_id':c['event_id'],'right':c['right'],'net':np.nan,'adverse_net':np.nan,
                         'entry_ask':np.nan,'exit_bid':np.nan,'missing_exit':False})
            continue
        ex=quotes.get((c['strike'],c['right'],pd.Timestamp(c['exit_time'])))
        missing=ex is None
        if missing: counters['missing_exit_zero_liquidation']+=1
        bid=0. if missing else ex[0]
        rows.append({'event_id':c['event_id'],'right':c['right'],'net':payoff(ent[1],bid),
                     'adverse_net':payoff(ent[1],bid,.02),'entry_ask':ent[1],
                     'exit_bid':bid,'missing_exit':missing})
    return rows

def clean_identity(f,ticker,day,name,counts):
        f['right']=f.right.astype(str).str.upper().replace({'C':'CALL','P':'PUT'})
        f['strike']=pd.to_numeric(f.strike,errors='coerce')
        f['timestamp']=parse_time(f.timestamp)
        f['expiration']=parse_time(f.expiration.astype(str)).dt.normalize()
        f['trade_date']=parse_time(f.trade_date.astype(str)).dt.normalize()
        valid=(f.symbol==ticker)&(f.expiration==day)&(f.trade_date==day)&(f.timestamp.dt.normalize()==day)&\
              f.right.isin(['CALL','PUT'])&np.isfinite(f.strike)&(f.strike>0)
        if name=='greek':
            valid &= (f.timestamp==f.timestamp.dt.floor('min')) &\
                     (f.timestamp>=day+pd.Timedelta(hours=9,minutes=30)) &\
                     (f.timestamp<=day+pd.Timedelta(hours=16))
        counts[name+'_invalid_identity']+=int((~valid).sum())
        f.drop(f.index[~valid], inplace=True)
        dup=f.duplicated(['strike','right','timestamp'],keep=False)
        counts[name+'_duplicate_keys']+=int(dup.sum())
        f.drop(f.index[dup], inplace=True)

def clean_sources(g, oi, ticker, day, counts):
    day=pd.Timestamp(day)
    for name,f in [('greek',g),('oi',oi)]: clean_identity(f,ticker,day,name,counts)
    g['underlying_timestamp']=parse_time(g.underlying_timestamp)
    age=(g.timestamp-g.underlying_timestamp).dt.total_seconds()
    good=(g.underlying_price>0)&np.isfinite(g.underlying_price)&age.between(0,60)
    counts['invalid_spot_rows']+=int((~good).sum())
    g.loc[~good,'underlying_price']=np.nan
    grouped=g.groupby('timestamp').underlying_price
    incons=grouped.nunique(dropna=True)>1
    counts['inconsistent_spot_minutes']+=int(incons.sum())
    spot=grouped.first()
    spot.loc[incons]=np.nan
    oi['open_interest']=pd.to_numeric(oi.open_interest,errors='coerce')
    bad_oi=(~np.isfinite(oi.open_interest))|(oi.open_interest<0)|(oi.open_interest%1!=0)
    counts['invalid_oi_rows']+=int(bad_oi.sum())
    oi=oi.loc[~bad_oi].copy()
    counts['invalid_quote_rows']+=int((~valid_quote(g)).sum())
    return g,oi,spot

def oi_snapshot(oi, stamp):
    return oi.loc[oi.timestamp<=stamp].sort_values('timestamp').drop_duplicates(['strike','right'],keep='last')

def chain_context(g,oi,stamp,spot,counts):
    chain=g.loc[g.timestamp==stamp].copy()
    available=oi_snapshot(oi,stamp)
    chain=chain.merge(available[['strike','right','open_interest']],on=['strike','right'],how='left',validate='one_to_one')
    counts['event_contracts_missing_oi']+=int(chain.open_interest.isna().sum())
    missing_oi=chain.open_interest.isna()
    chain['open_interest']=chain.open_interest.fillna(0.)
    iv=pd.to_numeric(chain.implied_vol,errors='coerce')
    valid=(iv>0)&(iv<=5)&np.isfinite(iv)
    counts['event_invalid_iv_rows']+=int((~valid).sum())
    expiry=stamp.normalize()+pd.Timedelta(hours=16)
    tau=max((expiry-stamp).total_seconds()/(365*86400),1e-10)
    sigma=iv.where(valid)
    d1=(np.log(spot/chain.strike)+.5*sigma*sigma*tau)/(sigma*np.sqrt(tau))
    chain['gamma_proxy']=np.exp(-.5*d1*d1)/(math.sqrt(2*math.pi)*spot*sigma*np.sqrt(tau))
    chain['gamma_density_proxy']=chain.gamma_proxy*chain.open_interest*100*spot*spot*.01
    context={'oi_missing_count':int(missing_oi.sum()),'oi_missing_fraction':float(missing_oi.mean()) if len(chain) else 1.}
    for side in ('CALL','PUT'):
        sub=chain.loc[chain.right==side]
        weights=sub.open_interest.to_numpy(float)
        context['oi_total_'+side]=float(weights.sum())
        for field in ('delta','vega','theta','implied_vol'):
            vals=sub[field].to_numpy(float)
            good=np.isfinite(vals)
            if field=='implied_vol': good &= (vals>0)&(vals<=5)
            den=weights[good].sum()
            context[field+'_oi_mean_'+side]=float(np.dot(weights[good],vals[good])/den) if den>0 else np.nan
        context['gamma_density_total_proxy_'+side]=float(sub.gamma_density_proxy.sum())
    return chain,context

def soft_fields(levels, weights, spot, prev, width, prefix):
    levels=np.asarray(levels,float); weights=np.asarray(weights,float)
    good=np.isfinite(levels)&np.isfinite(weights)&(weights>0)
    levels,weights=levels[good],weights[good]
    result={prefix+'_nearest':np.nan,prefix+'_approach':np.nan,prefix+'_rejection':np.nan,
            prefix+'_influence10':0.,prefix+'_influence25':0.,prefix+'_below10':0.,
            prefix+'_above10':0.,prefix+'_top_distance':np.nan,prefix+'_concentration':0.}
    if not len(levels): return result
    w=weights/weights.sum(); distances=(spot-levels)/width
    near=int(np.argmin(abs(distances))); old=(prev-levels[near])/width
    result[prefix+'_nearest']=float(distances[near])
    result[prefix+'_approach']=float(abs(old)-abs(distances[near]))
    result[prefix+'_rejection']=float((spot-prev)/width*np.sign(old))
    result[prefix+'_top_distance']=float(distances[np.argmax(w)])
    result[prefix+'_concentration']=float(np.max(w))
    for scale,label in ((.1,'10'),(.25,'25')):
        kernel=np.exp(-.5*(distances/scale)**2)
        result[prefix+'_influence'+label]=float(np.dot(w,kernel))
        if label=='10':
            result[prefix+'_below10']=float(np.dot(w,kernel*(distances>=0)))
            result[prefix+'_above10']=float(np.dot(w,kernel*(distances<0)))
    return result

def features_for(spot,chain,previous_chain,stamp,decision,ticker,bounds,context,shift):
    lo,hi=bounds; width=hi-lo; current=float(spot.loc[stamp])
    past=spot.loc[:stamp]
    result={'ticker':TICKERS.index(ticker),'clock':decision.hour*60+decision.minute,
            'ib_width_fraction':width/current,
            'realized_vol':float(np.log(past/past.shift(1)).std()),**context}
    ib_start=stamp.normalize()+pd.Timedelta(hours=9,minutes=30)
    result['ib_observed_minutes']=int(spot.loc[(spot.index>=ib_start)&(spot.index<ib_start+pd.Timedelta(hours=1))].notna().sum())
    for interval,n in ((5,12),(15,8)):
        for k in range(n):
            a=past.get(stamp-pd.Timedelta(minutes=k*interval),np.nan)
            b=past.get(stamp-pd.Timedelta(minutes=(k+1)*interval),np.nan)
            result[f'ret{interval}_{k}']=float(np.log(a/b)) if a>0 and b>0 else np.nan
        window=past.loc[stamp-pd.Timedelta(minutes=interval-1):stamp].dropna()
        result[f'candle{interval}_observed_fraction']=len(window)/interval
        for label,val in [('range',window.max()-window.min()),('body',window.iloc[-1]-window.iloc[0]),
                          ('upper',window.max()-max(window.iloc[0],window.iloc[-1])),
                          ('lower',min(window.iloc[0],window.iloc[-1])-window.min())]:
            result[f'candle{interval}_{label}']=float(val/width)
    prev=past.get(stamp-pd.Timedelta(minutes=5),np.nan)
    z={'ib_position':(current-lo-shift*width)/width}
    z.update(soft_fields(lo+RATIOS*width+shift*width,np.ones(len(RATIOS)),current,prev,width,'fib'))
    for side in ('CALL','PUT'):
        sub=chain.loc[chain.right==side]
        for field,prefix in [('open_interest','oi'),('gamma_density_proxy','gamma_proxy')]:
            name=prefix+'_'+side
            z.update(soft_fields(sub.strike.to_numpy()+shift*width,sub[field],current,prev,width,name))
            z[name+'_migration']=np.nan
            if previous_chain is not None:
                old=previous_chain.loc[previous_chain.right==side]
                now=sub.loc[np.isfinite(sub[field])&(sub[field]>0)]
                old=old.loc[np.isfinite(old[field])&(old[field]>0)]
                if len(now) and len(old):
                    z[name+'_migration']=float((now.loc[now[field].idxmax(),'strike']-old.loc[old[field].idxmax(),'strike'])/width)
    return result,z

def day_paths(ticker):
    return sorted((ROOT/ticker/'greeks'/'2023').glob('*/*.parquet'))

def read_day(path,ticker,counts,hashes):
    parts=path.stem.split('_')
    if len(parts)<4 or parts[1]!=parts[2]: return None
    date=parts[1]; oi=ROOT/ticker/'oi'/'2023'/date[4:6]/f'{ticker}_{date}_{date}_oi.parquet'
    if not oi.exists(): counts['missing_oi_file']+=1; return None
    for p in (path,oi):
        if str(p) not in hashes: hashes[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size}
    g=pq.read_table(path,columns=GREEK_COLS).to_pandas()
    o=pq.read_table(oi,columns=OI_COLS).to_pandas()
    return (*clean_sources(g,o,ticker,pd.Timestamp(date),counts),date)

def quote_dict(g,candidates=None):
    if candidates is not None:
        stamps={pd.Timestamp(c[field]) for c in candidates for field in ('entry_time','exit_time')}
        g=g.loc[g.timestamp.isin(stamps)]
    q=g.loc[valid_quote(g)]
    return {(r.strike,r.right,r.timestamp):(r.bid,r.ask) for r in q[['strike','right','timestamp','bid','ask']].itertuples(index=False)}

def process_day(item_args):
    events=[]; candidates=[]; labels=[]; hashes={}; counts=Counter(); iv_examples=[]
    ticker,path=item_args
    pa.set_cpu_count(1); pa.set_io_thread_count(1)
    for _ in range(1):
        item=read_day(path,ticker,counts,hashes)
        if item is None: continue
        g,oi,spot,date=item; day=pd.Timestamp(date); day_candidates=[]; previous=None
        shift=placebo_shift(ticker,date)
        vals=g.implied_vol[np.isfinite(g.implied_vol)&(g.implied_vol>0)&(g.implied_vol<=5)]
        if len(vals): iv_examples.append({'ticker':ticker,'date':date,'q10':float(vals.quantile(.1)),'median':float(vals.median()),'q90':float(vals.quantile(.9))})
        counts['days_read_'+ticker]+=1
        for minute in range(10*60+35,15*60+6,30):
            decision=day+pd.Timedelta(minutes=minute); stamp=decision-pd.Timedelta(minutes=1)
            counts['decision_candidates_'+ticker]+=1
            bounds=ib_bounds(spot,decision)
            if bounds is None: counts['invalid_ib_'+ticker]+=1; continue
            if stamp not in spot.index or not np.isfinite(spot.loc[stamp]): counts['missing_feature_spot_'+ticker]+=1; continue
            chain,context=chain_context(g,oi,stamp,float(spot.loc[stamp]),counts)
            if chain.empty: counts['missing_feature_chain_'+ticker]+=1; continue
            base,auth=features_for(spot,chain,previous,stamp,decision,ticker,bounds,context,0.)
            _,placebo=features_for(spot,chain,previous,stamp,decision,ticker,bounds,context,shift)
            previous=chain
            event_id=f'{ticker}_{date}_{minute}'
            events.append({'event_id':event_id,'date':date,'ticker_name':ticker,'decision':str(decision),
                           **{'p_'+k:v for k,v in base.items()},**{'a_'+k:v for k,v in auth.items()},**{'z_'+k:v for k,v in placebo.items()}})
            for side in ('CALL','PUT'):
                selected=contract_at(chain,stamp,side)
                if selected is None: counts['missing_feature_contract_'+ticker+'_'+side]+=1; continue
                c={'event_id':event_id,'date':date,'ticker_name':ticker,'right':side,'strike':float(selected.strike),
                   'decision':str(decision),'feature_time':str(stamp),'entry_time':str(decision+pd.Timedelta(minutes=1)),
                   'exit_time':str(decision+pd.Timedelta(minutes=31)),'selected_delta':float(selected.delta),
                   'placebo_shift_ib_units_diagnostic_only':shift}
                candidates.append(c); day_candidates.append(c)
        # Explicit stage boundary: no test payoff construction during feature build.
        if date<'20231001': labels.extend(labels_for(day_candidates,quote_dict(g,day_candidates),counts))
    return events,candidates,labels,hashes,counts,iv_examples

def initialize_worker(out):
    import faulthandler
    # Keep the native-fault diagnostic stream open for the process lifetime.
    global _fault_stream
    _fault_stream=(out/f'worker_{os.getpid()}_fault.log').open('x',encoding='utf-8')
    faulthandler.enable(_fault_stream,all_threads=True)
    pa.set_cpu_count(1); pa.set_io_thread_count(1)

def process_day_checkpoint(item_args):
    ticker,path,out=item_args
    date=path.stem.split('_')[1]
    write_json(out/f'worker_{os.getpid()}_current.json',{'ticker':ticker,'date':date,'stage':'reading'})
    result=process_day((ticker,path))
    part=out/'day_parts'/f'{ticker}_{date}.pkl'
    with part.open('xb') as f: pickle.dump(result,f,protocol=5)
    write_json(out/f'worker_{os.getpid()}_current.json',{'ticker':ticker,'date':date,'stage':'checkpoint_complete','sha256':sha(part)})
    return part

def build(out):
    events=[]; candidates=[]; labels=[]; hashes={}; counts=Counter(); iv_examples=[]
    files=[(t,p) for t in TICKERS for p in day_paths(t) if p.stem.split('_')[1]==p.stem.split('_')[2]
           and p.stem.split('_')[1] not in ('20230703','20231124')]
    # Ordered map preserves exact serial row and dictionary insertion order.
    (out/'day_parts').mkdir()
    jobs=[(ticker,path,out) for ticker,path in files]
    with ProcessPoolExecutor(max_workers=2,initializer=initialize_worker,initargs=(out,)) as pool:
        for idx,part in enumerate(pool.map(process_day_checkpoint,jobs,chunksize=1,buffersize=4)):
            with part.open('rb') as f: result=pickle.load(f)
            ev,ca,la,ha,co,iv=result
            events.extend(ev); candidates.extend(ca); labels.extend(la)
            hashes.update(ha); counts.update(co); iv_examples.extend(iv)
            if idx%25==0:
                ticker,path=files[idx]; date=path.stem.split('_')[1]
                print(json.dumps({'stage':'features','file':idx+1,'total':len(files),'ticker':ticker,'date':date,'events':len(events),'workers':2}),flush=True)
                write_json(out/'progress.json',{'stage':'features','file':idx+1,'total':len(files),'date':date,'workers':2})
    pd.DataFrame(events).to_parquet(out/'features.parquet',index=False)
    pd.DataFrame(candidates).to_parquet(out/'candidates.parquet',index=False)
    pd.DataFrame(labels).to_parquet(out/'train_validation_labels.parquet',index=False)
    write_json(out/'sources.json',hashes); write_json(out/'coverage.json',dict(counts)); write_json(out/'iv_unit_plausibility.json',iv_examples)
    return counts,hashes

def schedule(frame,threshold):
    if threshold is None: return frame.iloc[:0].copy()
    rows=[]; until={}
    for _,group in frame.sort_values(['decision','ticker_name','right']).groupby(['decision','ticker_name'],sort=True):
        row=group.sort_values(['prediction','right'],ascending=[False,True],kind='stable').iloc[0]
        decision=pd.Timestamp(row.decision); ticker=row.ticker_name
        if decision<until.get(ticker,pd.Timestamp.min) or row.prediction<=threshold: continue
        if not np.isfinite(row.net): continue
        rows.append(row.to_dict()); until[ticker]=pd.Timestamp(row.exit_time)
    return pd.DataFrame(rows,columns=frame.columns)

def fit_freeze(out):
    f=pd.read_parquet(out/'features.parquet'); c=pd.read_parquet(out/'candidates.parquet')
    y=pd.read_parquet(out/'train_validation_labels.parquet')
    joined=c.merge(f,on=['event_id','date','ticker_name','decision'],validate='many_to_one').merge(y,on=['event_id','right'],how='left',validate='one_to_one')
    train=joined.date<'20230701'; validation=(joined.date>='20230701')&(joined.date<'20231001')
    config=dict(n_estimators=150,num_leaves=15,max_depth=5,min_child_samples=80,learning_rate=.04,
                reg_lambda=10,n_jobs=2,random_state=SEED,verbosity=-1,deterministic=True,force_col_wise=True)
    frozen={}; predictions=[]
    common=[v for v in f.columns if v.startswith('p_')]
    for name,prefix in [('price',None),('authentic','a_'),('placebo','z_')]:
        columns=common+([v for v in f.columns if v.startswith(prefix)] if prefix else [])
        output=joined[c.columns.tolist()+['net','adverse_net','entry_ask','exit_bid','missing_exit']].copy()
        output['prediction']=np.nan
        for side in ('CALL','PUT'):
            mask=train&(joined.right==side)&joined.net.notna()
            if mask.sum()<80: raise RuntimeError(f'Insufficient train {name} {side}: {mask.sum()}')
            model=lgb.LGBMRegressor(**config)
            model.fit(joined.loc[mask,columns].to_numpy(float),joined.loc[mask,'net'])
            model.booster_.save_model(str(out/f'model_{name}_{side}.txt'))
            side_mask=joined.right==side
            output.loc[side_mask,'prediction']=model.predict(joined.loc[side_mask,columns].to_numpy(float))
        choices=[]
        for threshold in (0,5,10):
            ledger=schedule(output.loc[validation],threshold)
            counts=ledger.groupby('ticker_name').size().to_dict()
            choices.append({'threshold':threshold,'net':float(ledger.net.sum()),'counts':counts,
                            'qualifies':all(counts.get(t,0)>=10 for t in TICKERS)})
        qualified=[v for v in choices if v['qualifies']]
        winner=sorted(qualified,key=lambda v:(-v['net'],v['threshold']))[0] if qualified else {'threshold':None}
        frozen[name]={'threshold':winner['threshold'],'validation_count_gate':bool(qualified),'validation_choices':choices,'features':columns}
        output['representation']=name
        # Prediction artifact excludes every payoff field, including missingness.
        predictions.append(output.drop(columns=['net','adverse_net','entry_ask','exit_bid','missing_exit']))
    predictions=pd.concat(predictions,ignore_index=True)
    predictions.to_parquet(out/'frozen_predictions.parquet',index=False)
    write_json(out/'freeze.json',{'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'config':config,'representations':frozen,
                               'test_payoffs_constructed':False,'prediction_sha256':sha(out/'frozen_predictions.parquet'),
                               'models':{p.name:sha(p) for p in out.glob('model_*.txt')},
                               'features_sha256':sha(out/'features.parquet'),'candidates_sha256':sha(out/'candidates.parquet'),
                               'sources_sha256':sha(out/'sources.json'),'script_sha256':sha(__file__),
                               'spec_sha256':sha(Path(__file__).with_name('BENCHMARK_SPEC.md')),
                               'train_validation_labels_sha256':sha(out/'train_validation_labels.parquet')})
    return frozen

def verify_freeze(out):
    frozen=json.loads((out/'freeze.json').read_text(encoding='utf-8'))
    for filename,key in [('frozen_predictions.parquet','prediction_sha256'),('features.parquet','features_sha256'),
                         ('candidates.parquet','candidates_sha256'),('sources.json','sources_sha256'),
                         ('train_validation_labels.parquet','train_validation_labels_sha256')]:
        if sha(out/filename)!=frozen[key]: raise RuntimeError('Frozen artifact changed: '+filename)
    for name,digest in frozen['models'].items():
        if sha(out/name)!=digest: raise RuntimeError('Frozen model changed: '+name)
    if sha(__file__)!=frozen['script_sha256'] or sha(Path(__file__).with_name('BENCHMARK_SPEC.md'))!=frozen['spec_sha256']:
        raise RuntimeError('Frozen code/spec changed')
    return frozen

def test_labels(out,counts,hashes):
    verify_freeze(out)
    c=pd.read_parquet(out/'candidates.parquet'); c=c.loc[c.date>='20231001']; rows=[]
    for idx,((ticker,date),subset) in enumerate(c.groupby(['ticker_name','date'])):
        p=ROOT/ticker/'greeks'/'2023'/date[4:6]/f'{ticker}_{date}_{date}_greeks.parquet'
        if sha(p)!=hashes[str(p)]['sha256']: raise RuntimeError('Source changed before test opening: '+str(p))
        g=pq.read_table(p,columns=['symbol','expiration','trade_date','strike','right','timestamp','bid','ask']).to_pandas()
        clean_identity(g,ticker,pd.Timestamp(date),'greek',Counter())
        candidates=subset.to_dict('records')
        rows.extend(labels_for(candidates,quote_dict(g,candidates),counts))
        if idx%25==0: print(json.dumps({'stage':'test_payoffs','day':idx,'ticker':ticker,'date':date}),flush=True)
    pd.DataFrame(rows).to_parquet(out/'test_labels.parquet',index=False)
    write_json(out/'coverage.json',dict(counts))

def metrics(frame):
    result={'trades':len(frame)}
    for field,prefix in [('net','base'),('adverse_net','adverse')]:
        vals=frame[field] if len(frame) else pd.Series(dtype=float)
        gains=float(vals[vals>0].sum()); loss=float(-vals[vals<0].sum())
        result[prefix+'_net_usd']=float(vals.sum())
        result[prefix+'_win_rate']=float((vals>0).mean()) if len(vals) else None
        result[prefix+'_profit_factor']=gains/loss if loss>0 else None
    return result

def report(out,frozen,counts):
    pred=pd.read_parquet(out/'frozen_predictions.parquet')
    labels=pd.concat([pd.read_parquet(out/'train_validation_labels.parquet'),pd.read_parquet(out/'test_labels.parquet')])
    joined=pred.merge(labels,on=['event_id','right'],validate='many_to_one')
    results={}; ledgers=[]
    for name,settings in frozen.items():
        result={}
        for period,lo,hi in [('validation','20230701','20231001'),('test','20231001','20240101')]:
            subset=joined.loc[(joined.representation==name)&(joined.date>=lo)&(joined.date<hi)]
            ledger=schedule(subset,settings['threshold']); ledger['period']=period; ledgers.append(ledger)
            result[period]={'pooled':metrics(ledger),'tickers':{t:metrics(ledger.loc[ledger.ticker_name==t]) for t in TICKERS},'months':{}}
            for t in TICKERS:
                result[period]['months'][t]={}
                for month in sorted(subset.date.str[:6].unique()):
                    result[period]['months'][t][month]=metrics(ledger.loc[(ledger.ticker_name==t)&ledger.date.str.startswith(month)])
        results[name]=result
    all_ledgers=pd.concat(ledgers,ignore_index=True); all_ledgers.to_parquet(out/'ledger.parquet',index=False)
    test=all_ledgers.loc[all_ledgers.period=='test']
    # Fixed NYSE Q4 2023 full-session calendar, including days with no usable events.
    days=[d.strftime('%Y%m%d') for d in pd.bdate_range('2023-10-02','2023-12-29')
          if d.strftime('%Y%m%d') not in ('20231123','20231124','20231225')]
    daily=test.groupby(['date','representation']).net.sum().unstack(fill_value=0).reindex(index=days,columns=list(frozen),fill_value=0).fillna(0)
    daily.to_csv(out/'test_daily_net.csv')
    rng=np.random.default_rng(SEED); ci={}
    starts=rng.integers(0,len(days),size=(2000,math.ceil(len(days)/5)))
    indices=((starts[:,:,None]+np.arange(5))%len(days)).reshape(2000,-1)[:,:len(days)]
    for control in ('price','placebo'):
        delta=(daily.authentic-daily[control]).to_numpy(float)
        samples=delta[indices].sum(axis=1)
        ci['authentic_minus_'+control]={'observed_net_difference':float(delta.sum()),'paired_circular_5session_block_bootstrap_95ci_total_usd':[float(v) for v in np.quantile(samples,[.025,.975])], 'days':len(delta),'block_sessions':5,'resamples':2000}
    summary={'status':'COMPLETED_EXPLORATORY_DEVELOPMENT','untouched_outer':False,'live_parity_verified':False,
             'dealer_exposure_verified':False,'prior_close_semantics_verified':False,'technical_ready':False,'promotion_approved':False,
             'results':results,'paired_test_comparisons':ci,'coverage':dict(counts),'thresholds':frozen}
    write_json(out/'summary.json',summary)
    lines=['# Zone benchmark result — exploratory development','',
           'Completed one fixed 2023 train/validation/test experiment. This is previously seen development history, not untouched outer or live evidence.',
           '', '| Representation | Test trades | Base net USD | Adverse net USD | Base PF | Win rate |',
           '|---|---:|---:|---:|---:|---:|']
    for name in frozen:
        m=results[name]['test']['pooled']; wr=m['base_win_rate']; pf=m['base_profit_factor']
        lines.append(f"| {name} | {m['trades']} | {m['base_net_usd']:.2f} | {m['adverse_net_usd']:.2f} | {pf if pf is None else round(pf,3)} | {wr if wr is None else round(wr*100,2)}% |")
    lines+=['','Per-ticker test results:','', '| Representation | Ticker | Trades | Base net USD | Adverse net USD | Base PF |','|---|---|---:|---:|---:|---:|']
    for name in frozen:
        for ticker,m in results[name]['test']['tickers'].items():
            lines.append(f"| {name} | {ticker} | {m['trades']} | {m['base_net_usd']:.2f} | {m['adverse_net_usd']:.2f} | {m['base_profit_factor']} |")
    lines+=['','Paired circular five-session block bootstrap comparisons (2000 resamples):','',json.dumps(ci,indent=2),'',
            'Full month/ticker coverage, validation selection, source hashes, models and ledgers are preserved under '+str(out)+'.',
            '', 'Limitations: sampled spot extrema are not OHLC; historical quote/underlying timestamps are not observed arrival times; OI previous-close semantics are unverified for this vintage; BS gamma is a formula proxy with r=q=0, not measured dealer inventory; missing entries are excluded after fixed contract selection, missing exits liquidate at zero; no independent economic auditor or prospective shadow is completed. No profitability or promotion claim follows from this trial.']
    (Path(__file__).parent/'BENCHMARK_RESULT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,default=OUT); args=parser.parse_args()
    out=args.output
    out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,out/'zone_benchmark.py'); shutil.copy2(Path(__file__).with_name('BENCHMARK_SPEC.md'),out/'BENCHMARK_SPEC.md')
    write_json(out/'run_identity.json',{'started_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__),
               'spec_sha256':sha(Path(__file__).with_name('BENCHMARK_SPEC.md')),'test_outcome_access':'deferred_until_freeze',
               'versions':{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'lightgbm':lgb.__version__}})
    start=time.monotonic()
    counts,hashes=build(out)
    frozen=fit_freeze(out)
    print('FROZEN_BEFORE_TEST_PAYOFFS',flush=True)
    test_labels(out,counts,hashes)
    rehash={p:sha(p)==v['sha256'] for p,v in hashes.items()}
    write_json(out/'source_rehash.json',rehash)
    if not all(rehash.values()): raise RuntimeError('Source integrity failure at completion')
    report(out,frozen,counts)
    write_json(out/'completion.json',{'seconds':time.monotonic()-start,'source_count':len(hashes),'summary_sha256':sha(out/'summary.json')})
    print('COMPLETED_EXPLORATORY_DEVELOPMENT',flush=True)

if __name__=='__main__': main()
