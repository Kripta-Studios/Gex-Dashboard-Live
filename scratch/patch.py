import glob
import os

p = glob.glob(r"C:\Users\*\AppData\Roaming\Python\Python314\site-packages\torch\__init__.py")[0]
with open(p, "r", encoding="utf-8") as f:
    s = f.read()

s = s.replace("platform.system()", '"Windows"')
s = s.replace("platform.machine()", '"AMD64"')

with open(p, "w", encoding="utf-8") as f:
    f.write(s)
print("Patched PyTorch __init__.py!")
