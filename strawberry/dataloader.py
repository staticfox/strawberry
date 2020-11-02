import dataclasses
from asyncio import create_task, get_event_loop
from asyncio.futures import Future
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, List, Optional, TypeVar


T = TypeVar("T")
K = TypeVar("K")


@dataclass
class LoaderTask:
    key: Any
    future: Future


@dataclass
class Batch:
    tasks: List[LoaderTask] = dataclasses.field(default_factory=list)
    dispatched: bool = False

    def add_task(self, key: Any, future: Future):
        task = LoaderTask(key, future)
        self.tasks.append(task)

    def __len__(self) -> int:
        return len(self.tasks)


class DataLoader(Generic[T, K]):
    queue: List[LoaderTask] = []
    batch: Optional[Batch] = None

    def __init__(self, load_fn: Callable, max_batch_size: Optional[int] = None):
        self.load_fn = load_fn
        self.max_batch_size = max_batch_size

        self.loop = get_event_loop()

    def load(self, key: K) -> Awaitable:
        future = self.loop.create_future()

        batch = get_current_batch(self)
        batch.add_task(key, future)

        return future


def should_create_new_batch(loader: DataLoader, batch: Batch) -> bool:
    if (
        batch.dispatched
        or loader.max_batch_size
        and len(batch) >= loader.max_batch_size
    ):
        return True

    return False


def get_current_batch(loader: DataLoader) -> Batch:
    if loader.batch and not should_create_new_batch(loader, loader.batch):
        return loader.batch

    loader.batch = Batch()

    dispatch(loader, loader.batch)

    return loader.batch


def dispatch(loader: DataLoader, batch: Batch):
    async def dispatch():
        await dispatch_batch(loader, batch)

    loader.loop.call_soon(create_task, dispatch())


async def dispatch_batch(loader: DataLoader, batch: Batch) -> None:
    batch.dispatched = True

    keys = [task.key for task in batch.tasks]

    # TODO: check if load_fn return an awaitable and it is a list
    # TODO: check size

    values = await loader.load_fn(keys)
    values = list(values)

    for task, value in zip(batch.tasks, values):
        task.future.set_result(value)