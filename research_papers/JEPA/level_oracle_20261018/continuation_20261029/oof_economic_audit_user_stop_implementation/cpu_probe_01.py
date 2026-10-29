import ctypes,os,json
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.GetCurrentProcess.argtypes=[];k.GetCurrentProcess.restype=ctypes.c_void_p
k.GetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)];k.GetProcessAffinityMask.restype=ctypes.c_int
mask=ctypes.c_size_t();system=ctypes.c_size_t()
if not k.GetProcessAffinityMask(k.GetCurrentProcess(),ctypes.byref(mask),ctypes.byref(system)):raise ctypes.WinError(ctypes.get_last_error())
print(json.dumps(dict(mask=mask.value,threads=[os.environ[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')])))
