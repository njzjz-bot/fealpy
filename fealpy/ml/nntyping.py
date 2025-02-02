from typing import (
    List,
    Tuple,
    Callable,
    Union,
    Protocol,
    Any,
    Literal,
    TypeVar
)
from warnings import warn
import numpy as np
from torch import Tensor
import numpy as np
from numpy.typing import NDArray

TensorOrArray = Union[Tensor, NDArray]

TensorFunction = Callable[[Tensor], Tensor]
VectorFunction = Callable[[NDArray], NDArray]

Index = Union[int, bool, Tensor, slice, List, Tuple]
S: Index = slice(None, None, None)

ETypeName = Literal['node', 'edge', 'face', 'cell']
EType = Union[int, ETypeName]

_F = TypeVar("_F", bound=Callable[..., Any])


def deprecated(version: str, instead: str):
    def deprecated_(func: _F) -> _F:
        def wrapper(*args, **kwargs):
            obj = func.__class__.__name__ + "." + func.__name__
            msg = f"{obj} will be deprecated in version {version}, use {instead} instead."
            warn(msg, DeprecationWarning)
            return func(*args, **kwargs)
        return wrapper
    return deprecated_
