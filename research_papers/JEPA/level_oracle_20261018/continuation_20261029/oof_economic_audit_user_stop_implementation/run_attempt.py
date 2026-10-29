from pathlib import Path
import ctypes,hashlib,json,os,subprocess,sys,time
import psutil
code=Path(sys.argv[1]).resolve()
root=Path(__file__).parent
attempt=root/sys.argv[2]
attempt.mkdir(exist_ok=False)
psutil.Process().cpu_affinity([0])
assert psutil.Process().cpu_affinity()==[0]
class Memory(ctypes.Structure):
 _fields_=[("length",ctypes.c_ulong),("load",ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ("total","ram","total_commit","commit","v","fv","ex")]
m=Memory();m.length=ctypes.sizeof(m)
assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
assert m.ram>=2000000000 and m.commit>=2000000000
files={}
for name in ('launch_oof_economic_audit_user_stop_continuation_20261029.py','test_launch_oof_economic_audit_user_stop_continuation_20261029.py'):
 p=code/name
 if p.exists():
  data=p.read_bytes(); (attempt/name).write_bytes(data);files[str(p)]=hashlib.sha256(data).hexdigest()
command=[sys.executable,'-m','pytest',str(code/'test_launch_oof_economic_audit_user_stop_continuation_20261029.py'),'-q',*sys.argv[3:]]
env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
start=time.time()
with (attempt/'stdout.log').open('xb') as out,(attempt/'stderr.log').open('xb') as err:
 child=subprocess.Popen(command,cwd=code,env=env,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
 ret=child.wait()
result=dict(exit_code=ret,command=command,files=files,started_epoch=start,finished_epoch=time.time(),available_ram_bytes=m.ram,free_commit_bytes=m.commit,cpu_affinity=[0],threads=1)
result['logs']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (attempt/'stdout.log',attempt/'stderr.log')}
(attempt/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2));print((attempt/'stdout.log').read_text(encoding='utf-8'));print((attempt/'stderr.log').read_text(encoding='utf-8'))
sys.exit(ret)
