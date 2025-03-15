# 1.4.6

## Notice for using dynamic libraries

Return values other than int, float, long and char* (any other char variation)
is not directly supported and may require using the "#include <Python.h>"
header. This is also true for parameters (or arguments).

## Using dynamic libraries

You can now use C in DPL!
Using dynamically linked libraries for windows and
shared object files in posix compliant systems!

Look at the example at `example/dl.dpl`
as well as the C code in `example/test.c`

## Notice

As of now DPL will have a code
standard requirements.
In STANDARDS.md

## Using DLL and SO files

DPL now supports using dynamic libraries.

`test.dpl`
```DuProL
cdef "void hello();"
dlopen test "./test.so"
cget hello :test

ccall :hello
```
`test.c` => `test.so`
```C
#include <stdio.h>

void hello() {
    printf("Hello, world!\n");
}
```

## New template syntax

```DuProL
&use {std/text_io.py}
&use {std/types.py}

template Person
    define name as :types.str = "default_name"
    define age  as :types.int = 0
    define data as :types.dict
end

from_template :Person Andrew
    name $name
    age 15
    data [dict [this=what]]
end

io:println :Andrew

# Inline template (not recommended as it is hard to read)

from_template [dict [name=:types.str][age=:types.int][data=:types.dict]] Andrew
    name $name
    age 15
    data [dict [this=what]]
end

io:println :Andrew
```

## Aliases when importing

When using `&use` you can add `as name` at the end.
For example `&use {some.py} as alias`.
See `example/alias.dpl` for more details.

## Variable Handling

Auto resolution of names (being able to
implicitly use global variables) can be
disabled by setting `_meta.debug.allow_automatic_global_name_resolution`
to `0` or any falsy value.

```DuProL
&use {std/text_io.py}

set _meta.debug.allow_automatic_global_name_resolution 0
set my_var "Global Variable"

fn test
    io:println :my_var
    io:println :_global.my_var
end
test
```

## Added new functions

The `exec` and `sexec` functions were added,
these functions can run DPL code on runtime.
```DuProL
set code "&use {std/text_io.py}\nio:println \"Hello!\""
exec :code "string" [?list !dict]
```

To not propagate the errors through the main
program. Use `sexec`
```DuProL
set code "&use {std/text_io.py}\nio:println \"Hello!\""
sexec err :code "string" [?list !dict]
io:println :err
```

The `[?list !dict]` is the frame stack.
In python its just `[{}]`.

If you want to pass the current frame stack,
use `:_frame_stack` which has the execution
context of the main program.
```DuProL
&use {std/text_io.py}
set code "io:println \"Hello!\""
exec :code "string" :_frame_stack
```

## Another Update to the REPL

Added more features to the completer,
it now suggests directives.

```
DPL REPL for DPL v1.4.6
Python 3.11.4 (main, Sep 30 2023, 10:54:38) [GCC 11.4.0]
>>> &use {
           &use {std}
           &use {std/array_utils.py}
           &use {std/dicts.py}
           &use {std/file_io.py}
           &use {std/include-py.txt}
           &use {std/text_io.py}
           &use {std/types.py}
           &use {std/strings.py}
           &use {std/tests.py}
           &use {std/to_py.py}
           &use {std/to_dict.py}
           &use {std/typed_vars.py}
```

## 1.4.6 REPL

The REPL now supports code suggestions!
Or at least auto completion.


```
DPL REPL for DPL v1.4.6
Python 3.11.4 (main, Sep 30 2023, 10:54:38) [GCC 11.4.0]
>>> &use {std}
>>> io:
        io:print
        io:printf
        io:println
        io:rawprint
        io:rawprintln
        io:input
        io:setOutputFile
        io:rawoutput
        io:flush
        io:open
        io:seek
        io:read
        io:write
        io:append
        io:close
```

## Using `&use`, `&use:luaj`, `&include` and `&includec` on directories

Its pretty simple to setup.
Just write a "include-[lang].txt" file.
For example we\'ll use python.
In that case we will write "include-py.txt".
In that file we will list the files we want
to export.

The directory should look like this
```
example
├── file1.py
├── file2.py
├── file3.py
└── include-py.txt
```

If you want to only include `file1.py` and `file3.py`
but not `file2.py` your include file should look like
this:
```
file1.py
file3.py
```

You can have comments.

```
# file1 does ...
file1.py
# file2 needs to be manually included.
# file3 does ...
file3.py
```

You can also print stuff out.
```
#:Print with meta data
#?Print without meta data.
```

## New Syntax!

```DuProL

# Embed a file.
&embed "test.txt" as text_txt
# As a byte array
&embed_binary "test.bin" as text_bin

-- Multiline comments!
new expressions
... [...]
--

# Lists
set list [?list item1 item2]
## Indexing a list
pass [:list 0]
## Indexing strings
pass ["oh" -1] # grab last character

fn dangerous_func
    raise :_meta.err.RUNTIME_ERROR "Oh no!"
end

# Call it safely
safe dangerous_func
# Or if youre expecting a return value
scatch [?list error values] dangerous_func
io:println :error :values


```

## Lua JIT!

DPL can now interact with Lua through
Lua JIT or "luaj" internally.

You can use lua modules by using the new
`&use:luaj` directive.

### Example DPL/Lua Module

```Lua

if type(api) == "nil" then
    -- Make sure only DPL can use this
    error("DPL Module!")
end

ext = api.dpl.pycall(
    api.dpl.extension,
    null,
    {
        name = "scoped_name", -- takes precedence over meta_name
        meta_name = "mangled_name"
    }
)

ext = ext:add_func("func_name")
(function(frame, locdir, ...)
    -- do stuff here
    return api.type.tuple({})
end)


```

## Match statements!

```DuProL
&use {std/text_io.py}

set test "Hello"

# New match statements!
match :test
    as this
    with "Hello"
        io:println :this
    end
    with "Hello world!"
        io:println "Hello user!"
    end
    case [[Type :this] == "int"]
        io:println "Wait a number?"
    end
    # invalid code
    io:println :this
end
```

## Bench Marks

```DuProL
for i in (Range 1000)
pass "test"
end
```

```
Benchmark 1: 100
  Time (mean ± σ):     679.3 ms ±  56.2 ms    [User: 575.1 ms, System: 103.0 ms]                                                    Range (min … max):   583.5 ms … 724.6 ms    10 runs            
  Warning: Ignoring non-zero exit code.
```

For some reason it was exiting with a non zero
exit code and I had to double check the source
but it has no errors and was running fine.

Keep in kind that this is heavily dependent
on the platform and the hardware used!

Specs:

```
Device:    Oppo A18
OS:        Termux (Android 14)
RAM:       4Gb
Processor: Helio G85
Python 3.12.9 (main, Feb  4 2025, 22:30:28) [Clang 18.0.3]
```

# Deprecation!

`import` statements are now nonexistent!
As well as the `dpl install` command!

# Added new command

`dpl docs file.mmu` and
`dpl docu file.mmu`

# New underlying mechanisms

`_meta.str_intern` has been added.
It will intern the string with `sys.intern`
thus optimizing freaquently used strings.

# 1.4.5 New features

Added the elipsis constant `...`
which will be used as empty statements
or empty expressions.

Implemented and rewrote some of the logic for
the optimizer.

# 1.4.5 Rewriting the codebase

Some of the instruction implementations
have been rewritten for performance.
The benchmarks will be here soon.

Any contributions to the codebase is
very much appreciated.

Before making a merge/pull request please
send the zip at `darrenchasepapa@gmail.com`.
I dont trust github to provide the changes.

Your credits will be added here.

# 1.4.5 Added new for loop syntax

```DuProL
for index, value in :list
    io:println '${index}: {value}'
end
```

# 1.4.5 Minor changes

`import*` is now removed.
The new directory structure in which all
standard library modules are in "std".
This is to facilitate order and to avoid
conflicts with future packages.

`dpl package install `<user> <repo> <branch>`,
`dpl package installto: <path_dest> `<user> <repo> <branch>`
and
`dpl package remove <package_name>`
has been added.

# 1.4.4 Patch Alpha

The memoization had some bugs in it.
The example too had some logic errors.
It is now fixed.

From my device `mcatch [] memoize_fact 28000`
in the first pass is `8s` while in the second
`below 1ms`

# Repo Notice

The master branch will always be the bleeding edge branch.

# Changes to 1.4.4

A major change in syntax.
Instead of `&use <standard_lib.py>` the new
syntax is `&use {standard_lib.py}`

Operations +, -, *, /, >, < must now have spaces.
Meaning `(2+2)` must now be `(2 + 2)`, I infer that
most people use the latter anyways.

Memoization has been builtin but not automatic.
It is controlled by the user and can only be used
by functions that can return.

(previous execution times removed as they could
fall under misinformation)

```DuProL
# DEPENDS ON DEVICE
# AND MUSNT BE TAKEN AT FACE VALUE

&use {text_io.py}

fn memoize_fact n
    if (:n <= 1)
        return 1
    end
    # mcatch stands for [m]emoized [catch]
    mcatch [f] _global.memoize_fact (:n - 1)
    return (:n * :f)
end

fn fact n
    if (:n <= 1)
        return 1
    end
    catch [f] _global.fact (:n - 1)
    return (:n * :f)
end

START_TIME
catch [this] memoize_fact 20000
STOP_TIME
LOG_TIME

START_TIME
catch [this] fact 20000
STOP_TIME
LOG_TIME

START_TIME
catch [this] memoize_fact 18000
STOP_TIME
LOG_TIME

START_TIME
catch [this] fact 18000
STOP_TIME
LOG_TIME
```

We might introduce a version bump to 1.5.x
Although we are going to be consistent so
1.4.4 might be the final choice.

# Another set of features

DPL now allows commas to seprate arguments!
Its still optional though.

```DuProL
set this [0,1,2,3]
# is just
set this [0 1 2 3]
```

Since the parser has evolved we can
finally not use spaces in our expressions!

```DuProL
set result (90+90)
```

# 1.4.4 Modules

New Modules:
- array_utils.py
```
    Contains functions and methods to
    join two arrays, reverse an array,
    and to slice an array.
```
New Functions:
- io:printf in text_io.py
```
    Has a simple formatter.
    io:printf "%N" value0 value1 ... valueN
    where N is the index of a value.
    Example:
    set test (90+90)
    io:printf "Result: %0\n" :test
```
# 1.4.4 In-comming Release

Release Date: March 15, 2025
Features:
- :white_check_mark: Dead code optimization.
- :white_check_mark: Profiling.
- :stop_sign: Generators
- :white_check_mark: Formatted strings.

# Repo Notice As Of Feb 9 2025

Every new versions including patches
will be made on separate branches.

This is to improve security.

# 1.4.3 Patch Alpha (1.4.3-a)

Added new info.

# Fixes 1.4.3

Fixed a bug that misinterpreted hex literals in strings.
Example: "This is a test" becomes "This is 10 test"
It is now fixed by making strings parsed before the hex literals.

Benchmarks (not totally accurate)
```
Device:    Oppo A18
OS:        Android 14
RAM:       4Gb
Processor: Helio G85
Python 3.11.4 (Pydroid3)
```

1 million loop
    
With string parsing
```
1.4.3: 11.812s
1.4.2: 17.017s
```

Code:
```DuProL
    START_TIME
    for i in (Range 1,000,000)
        # This tests the string parsing speed
        pass "test"
    end
    STOP_TIME
    LOG_TIME
```
    
Without string parsing
```
1.4.3: 65.914ms
1.4.2: 80.352ms
```
    
Code:
```DuProL
    START_TIME
    for i in (Range 1,000,000)
    end
    STOP_TIME
    LOG_TIME
```
    
Since the string parsing is now on the
preruntime side. The loops are a ton more
faster.

# Additions 1.4.0 - DuProL/Python API Update!

A "dpl" and "modules" class is defined on import of that script.
This is to make the global scope more clean.

Heres how its organized. Any DPL related modules will be in `dpl`
While modules like os, sys, time, ... and any other modules that are imported
by DPL will be found there.

You can now use `dpl.info.isCompat` to check version compatibility.
It accepts a tuple with three integers. (major, minor, patch)
It is calculated against "dpl.info.VERSION_TRIPLE". "dpl.info.VERSION" is
a `Version` object which has methods to calculate compatibility.

## More changes

    Drastic rewriting of the standard library.

# Additions 1.3.0

Incomplete documentation.

## Renamed expect-then to expect_then

This is to make the instructions more consistent.
Some instructions, this included, may be subjected to future changes.
Maybe it will be switch to camel case formatting.

## Renaming of most extensions

To enfore the new naming conventions for DuProL,
most python functions has been renamed.
_mods will now be deprecated as the new scope mechanisms simply
doesnt need it anymore.

## Posible Future Features

1. HTTPS requests.

2. More threading stuff? (partially implemented)

3. Slight overhauls:

    1. Actual parsing. (rejected)

    2. More standard libraries.

4. Built in linting. (Not Sure)

5. Better static typing support. (implemented)


# Additions 1.2.0

Incomplete documentation.

## Regarding This Repo

DuProL will now follow a semantic version format.

    "Major.Minor.Patch"

This file will be updated per update.

## Fixes 'N Stuff

1. Updated paths on linux. No more over complication

2. Added this file.

3. Made it so that when a local var isnt found it looks for it

   in the global scope.

4. Added new methods "append" and "pop"



Used like this 

```

import "text_io.py"

set array []

pass (append :array 90)

# prints array after it has appended the 80 so it should be [90, 80]

io println (append :array 80)

```



## Posible Future Features

1. HTTPS requests.

2. More threading stuff?

3. Slight overhauls:

    1. Actual parsing and stuff.

    2. More standard libraries.

