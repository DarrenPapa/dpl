from typing import Any


class arguments_handler:
    def __init__(self, args: list[Any] | None, kwargs: dict | None) -> None:
        self.args = args
        self.kwargs = kwargs

    def parse(self, args) -> None:
        if self.kwargs is None:
            self.kwargs = {}
        if self.args is None:
            self.args = []
        for i in args:
            if isinstance(i, dict):
                self.kwargs.update(i)
            else:
                self.args.append(i)

    def call(self, func) -> None:
        return func(*self.args, **self.kwargs)

    def __repr__(self) -> str:
        return f"<arguments_handler({self.args!r}, {self.kwargs!r})>"
