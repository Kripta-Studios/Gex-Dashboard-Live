import math,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import session_actor_clock_semantics_validation as lab
import pytest
g=lab.graphs()[-1]
params=[0.,math.log(.4/.6),0.,0.,0.,math.log(.25/.75),0.,0.]
p,d=lab.policy(g,params)
r=lab.enumerate_paths(g,p,d)
assert math.isclose(r['objective'],-.5,abs_tol=1e-12)
assert math.isclose(r['pnl'],1.75,abs_tol=1e-12)
assert math.isclose(r['no_fill'],.75,abs_tol=1e-12)
assert math.isclose(r['attempts'],.65,abs_tol=1e-12)
expected=[0.,0.,0.,0.,-1.875,1.875,0.,0.]
for actual in (r['gradient'],lab.adjoint(g,p,d)):
    assert all(math.isclose(x,y,abs_tol=1e-12) for x,y in zip(actual,expected,strict=True))
theta=[.2,-.3,.4]
p,d=lab.policy(g,theta,True)
r=lab.enumerate_paths(g,p,d)
q=1/(1+math.exp(-(.1*.2-1.25*(-.3)+1.4*.4)))
assert math.isclose(r['objective'],10*q-3,abs_tol=1e-12)
expected=[10*q*(1-q)*c for c in (.1,-1.25,1.4)]
for actual in (r['gradient'],lab.adjoint(g,p,d)):
    assert all(math.isclose(x,y,abs_tol=1e-12) for x,y in zip(actual,expected,strict=True))
print('INDEPENDENT_LITERAL_RETRY_VALUES_AND_SHARED_CHAIN_PASS')
raise SystemExit(pytest.main(['-q','-p','no:cacheprovider',str(Path(sys.argv[1])/'test_session_actor_clock_semantics_validation.py'),'-k','retry_counterexample or full_and_short_clock or last_decision_fill or attempts_not_fills or filled_blocks or enumeration_is_independent or status_does_not_remove']))
