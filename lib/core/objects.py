# A simple way of making objects and methods n stuff...

from . import varproc
from . import constants

id_tracker = 0


def set_repr(frame, name="???", type_name=None, repr=None):
    global id_tracker
    if "_internal" not in frame:
        frame["_internal"] = {
            "name": name,
            "type": f"type:{type_name or name}",
            "docs": "An object.",
            "id": id_tracker,
        }
    if "_im_repr" not in frame:
        frame["_im_repr"] = {  # define a boring default _im_repr
            "name": 0,
            "args": [],
            "defs": 0,
            "docs": f"Default internal method for ({name}).",
            "self": 0,
            "body": [
                (
                    0,
                    "_internal",
                    "return",
                    (repr or f"<{type_name or 'Object'} {name} ID: {id_tracker}>",),
                )
            ],
        }
    id_tracker += 1
    return frame


def make_function(name, body, params):
    global id_tracker
    id_tracker += 1
    return set_repr(
        {
            "name": name,
            "body": body,
            "args": params,
            "self": constants.nil,
            "docs": f"Function. ({name!r})",
            "defs": {},
            "memoize": {},
            "id": id_tracker - 1,
            "capture": constants.nil,
        },
        name,
        "builtin-function-object",
    )


def make_method(name, body, params, self):
    global id_tracker
    id_tracker += 1
    return set_repr(
        {
            "name": name,
            "body": body,
            "args": params,
            "self": self,
            "docs": f"Method of {varproc.rget(self, '_internal.name')}. ({name})",
            "defs": {},
            "id": id_tracker - 1,
        },
        name,
        "builtin-method-object",
    )


def make_object(name):
    global id_tracker
    id_tracker += 1
    return set_repr(
        {
            "_internal": {
                "name": name,
                "type": f"type:{name}",
                "docs": f"An object. ({name})",
                "id": id_tracker - 1,
            }
        },
        name,
        "builtin-object:Object",
    )
