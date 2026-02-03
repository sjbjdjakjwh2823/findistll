import asyncio
import inspect


def pytest_pyfunc_call(pyfuncitem):
    test_func = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_func):
        return None

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(test_func(**pyfuncitem.funcargs))
    finally:
        loop.close()
    return True
