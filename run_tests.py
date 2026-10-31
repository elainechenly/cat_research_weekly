"""Tiny test runner (works without pytest). Usage: python run_tests.py"""
import importlib, pkgutil, sys, traceback
sys.path.insert(0, ".")
ok = bad = 0
for mod in sorted(m.name for m in pkgutil.iter_modules(["tests"]) if m.name.startswith("test_")):
    t = importlib.import_module(f"tests.{mod}")
    for n in sorted(dir(t)):
        if n.startswith("test_"):
            try: getattr(t, n)(); ok += 1
            except Exception: bad += 1; print("FAIL", mod, n); traceback.print_exc()
print(f"{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
