# Flying Spaghetti Monster / Finite State Machine

import abc
import asyncio
import subprocess
from enum import Enum, auto
from typing import Optional, Dict, Sequence, List, Union

import paco  # type: ignore

from qemu_android_test_orchestrator.shared_state import SynchronizedObject
from qemu_android_test_orchestrator.utils import Color, balloon_stat


class State(Enum):
    # Initial state
    START = auto()
    # Once reached, QEMU is up and running
    QEMU_UP = auto()
    # Once reached, VM is connected to the network
    NETWORK_UP = auto()
    # Once reached, ADB is connected and usable
    ADB_UP = auto()
    # Once reached, job was run and has terminated
    JOB = auto()
    # Some job transition failed - the manager FSM will have this state but the workers will keep their own, so they
    # can still at least try to stop again
    UNKNOWN = auto()
    # Once reached, everything is stopped
    STOP = auto()


_allowed_transitions: Dict[State, Sequence[State]] = {
    State.START: (State.QEMU_UP, State.STOP),
    State.QEMU_UP: (State.NETWORK_UP, State.STOP),
    State.NETWORK_UP: (State.ADB_UP, State.STOP),
    State.ADB_UP: (State.JOB, State.STOP),
    State.JOB: (State.STOP,),
    State.UNKNOWN: (State.STOP,),
    State.STOP: ()
}


class TransitionResult(Enum):
    NOOP = auto()
    DONE = auto()
    # On error, an exception is raised


class InvalidTransitionError(Exception):
    def __init__(self, before: State, after: State) -> None:
        super().__init__(f"Invalid transition: {before} -> {after}")


class AbstractFSM(abc.ABC):
    @property
    def cur_state(self) -> State:
        return self._cur_state

    @property
    def wanted_state(self) -> Optional[State]:
        return self._wanted_state

    @property
    def is_pending(self) -> bool:
        return self._wanted_state is not None

    def __init__(self) -> None:
        self._cur_state: State = State.START
        self._wanted_state: Optional[State] = None

    def check_transition(self, wanted_state: State) -> None:
        if wanted_state not in _allowed_transitions[self.cur_state]:
            raise InvalidTransitionError(self.cur_state, wanted_state)

    @abc.abstractmethod
    async def transition(self, wanted_state: State) -> TransitionResult:
        raise NotImplemented


class ManagerFSM(AbstractFSM):
    def __init__(self) -> None:
        super().__init__()
        self.__workers: List['WorkerFSM'] = []

    def register_worker(self, worker: 'WorkerFSM') -> None:
        self.__workers.append(worker)

    async def transition(self, wanted_state: State) -> TransitionResult:
        self.check_transition(wanted_state)
        self._wanted_state = wanted_state

        coro_names: List[str] = [i.name for i in self.__workers]
        coro_results: List[Optional[TransitionResult]] = [None for _ in self.__workers]

        def pretty_result(result: Union[TransitionResult, Exception, None]) -> str:
            result_names = {
                TransitionResult.DONE: Color.YELLOW + "Action performed" + Color.RESET,
                TransitionResult.NOOP: Color.GREEN + "Ok" + Color.RESET,
                None: "Pending"
            }

            if isinstance(result, Exception):
                return Color.RED + "ERROR! Shutting down" + Color.RESET
            return result_names[result]

        def print_progress_update(task: asyncio.Task = None, result: Optional[TransitionResult] = None) -> None:
            longest_name_len = max(map(len, coro_names)) + 1
            if not task:
                return
            name = coro_names[task.index]
            print(f"{Color.CYAN}{(name + ':').ljust(longest_name_len)}{Color.RESET} {pretty_result(result)}")

        def register_result(task: asyncio.Task, result: Union[TransitionResult, Exception]) -> None:
            coro_results[task.index] = result
            print_progress_update(task, result)

        message = f"Current state is {self.cur_state}, next step: {wanted_state}"
        print(Color.BROWN + ('-' * len(message)))
        print(message)
        print("Trying to reach next state, waiting for worker rendezvous")
        print("Memory usage:")
        subprocess.Popen(['free', '-h']).wait()
        balloon_stat()
        print(('-' * len(message)) + Color.RESET)
        print_progress_update()

        try:
            concurrent = paco.concurrent(limit=len(self.__workers))
            # noinspection PyTypeChecker
            concurrent.on('task.finish', register_result)
            # noinspection PyTypeChecker
            concurrent.on('task.error', register_result)
            for worker in self.__workers:
                concurrent.add(worker.transition, wanted_state)
            # If we don't retrieve the exception manually, two exceptions are thrown making the error more confusing
            done, pending = await concurrent.run(return_when='FIRST_EXCEPTION', return_exceptions=True)
            for task in list(done) + list(pending):
                exc = task.exception() or isinstance(task.result(), Exception) and task.result() or None
                if exc:
                    raise exc
            self._cur_state = wanted_state
        except Exception:
            self._cur_state = State.UNKNOWN
            try:
                await concurrent.cancel()
            except (AttributeError, TypeError):
                pass
            raise
        finally:
            self._wanted_state = None

        return TransitionResult.NOOP


class WorkerFSM(AbstractFSM):
    def __init__(self, shared_state: SynchronizedObject) -> None:
        super().__init__()
        self.shared_state = shared_state

    @property
    @abc.abstractmethod
    def name(self) -> str:
        raise NotImplemented

    @abc.abstractmethod
    async def exit_state(self, state: State) -> TransitionResult:
        raise NotImplemented

    @abc.abstractmethod
    async def enter_state(self, state: State) -> TransitionResult:
        raise NotImplemented

    async def transition(self, wanted_state: State) -> TransitionResult:
        self.check_transition(wanted_state)
        self._wanted_state = wanted_state

        try:
            exit_result = await self.exit_state(self._cur_state)
            enter_result = await self.enter_state(wanted_state)
            self._cur_state = wanted_state
            return \
                TransitionResult.DONE if TransitionResult.DONE in (exit_result, enter_result) else \
                    TransitionResult.NOOP
        finally:
            self._wanted_state = None
