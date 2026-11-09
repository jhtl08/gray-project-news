import importlib
import sys


def test_import_laya_processes_does_not_call_get_router():
    # Remove cached modules to observe import side effects cleanly.
    for name in list(sys.modules):
        if name == "laya" or name.startswith("laya.") or name == "laya_processes":
            del sys.modules[name]

    import laya_processes

    assert "laya" not in sys.modules
    assert getattr(laya_processes, "_router", None) is None
    # get_router should be callable but not invoked during import.
    assert callable(laya_processes.get_router)
