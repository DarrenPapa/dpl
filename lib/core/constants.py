from . import state

nil = state.bstate("nil")
none = state.bstate("none")
elipsis = state.bstate("...")
any = state.bstate("types:any")
true = 1
false = 0

constants = (nil, none, int)
constants_false = (nil, none, 0, None)
