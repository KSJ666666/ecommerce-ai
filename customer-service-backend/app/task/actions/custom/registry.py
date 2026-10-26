import importlib
import inspect
import pkgutil
from types import ModuleType

from app.task.actions.base import Action
from app.task.actions.runner import ActionRunner


def register_custom_actions(
    action_runner: ActionRunner,
    package_name: str = "app.task.actions.custom",
) -> ActionRunner:
    package = importlib.import_module(package_name)

    for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__, prefix=f"{package.__name__}."):
        if is_pkg:
            continue
        module = importlib.import_module(module_name)
        for action in _discover_actions(module):
            action_runner.registry.register(action)

    return action_runner


def _discover_actions(module: ModuleType) -> list[Action]:
    actions: list[Action] = []
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if not issubclass(obj, Action) or obj is Action:
            continue
        if obj.__module__ != module.__name__:
            continue
        actions.append(obj())
    actions.sort(key=lambda action: action.name)
    return actions
