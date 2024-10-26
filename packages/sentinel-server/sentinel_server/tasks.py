import asyncio
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from functools import partial
from typing import Callable

process_pool_executor = ProcessPoolExecutor()
thread_pool_executor = ThreadPoolExecutor()


async def _run(executor: Executor, callable: Callable, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, partial(callable, *args, **kwargs))


async def run_in_thread(callable: Callable, *args, **kwargs):
    """
    Run the given callable in a separate thread from a thread pool.
    """
    return await _run(thread_pool_executor, callable, *args, **kwargs)


async def run_in_process(callable: Callable, *args, **kwargs):
    """
    Run the given callable in a separate process from a process pool.
    """
    return await _run(process_pool_executor, callable, *args, **kwargs)
