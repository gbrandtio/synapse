from __future__ import annotations
import json, os, subprocess, time
from pathlib import Path
import tree_sitter_language_pack as pack
ROOT = Path(__file__).parent
out = {}
print([a for a in dir(pack) if 'cache' in a.lower() or 'download' in a.lower() or 'config' in a.lower()])
pack.configure(cache_dir=str(ROOT/".cache"/"ts")) if hasattr(pack,'configure') else None
langs = ["python","javascript","typescript","tsx","java","c","cpp","csharp","go","rust","ruby","php","dart","kotlin","swift","bash","html","css","json","yaml","sql","markdown"]
ok = []
t=time.perf_counter()
for l in langs:
    try:
        pack.get_parser(l); ok.append(l)
    except Exception as e:
        print("fail", l, repr(e)[:100])
out["ts_loaded"]=len(ok); out["ts_secs"]=round(time.perf_counter()-t,1)
c=ROOT/".cache"/"ts"
out["ts_cache_mb"]=round(sum(f.stat().st_size for f in c.rglob("*") if f.is_file())/1048576,1) if c.exists() else None
print(out)
