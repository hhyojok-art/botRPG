import importlib,traceback,sys
try:
    m = importlib.import_module('dashboard.app')
    print('MODULE_OK')
    print('attrs=', [a for a in dir(m) if not a.startswith('__')])
    print('HAS_APP=', hasattr(m,'app'))
    print('app=', type(getattr(m,'app',None)))
except Exception:
    traceback.print_exc()
    sys.exit(1)
