import sys, pathlib, importlib
sys.path.insert(0,str(pathlib.Path('.').resolve()))
mod = importlib.import_module('cogs.achievements')
importlib.reload(mod)
print('BADGES count:', len(mod.BADGES))
for k,v in list(mod.BADGES.items())[:10]:
    print(k, '->', v[0])
