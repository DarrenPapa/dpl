# DPL - Dumb Programing language

## Info

Created by: Darren Chase Papa<br>
Written using: Python 3.13 (At least 3.10 and above)

## Hello world

In pursuit of making the parser faster, and also smaller.
We modularized the functions, since DPL can interface with python,
we made extensions, one of which is used here (`text_io.py`)

```
# By default the search path is the library path
import "text_io.py"

io println "Hello, world!"
```

## Literals

- strings: `"Hello there!"`
- integers: `1,000,000 (yes commas are allowed)`
- floats: `1,000.00`
- list: `[0 1 2 3 4 5 6 7 8 9 "Also strings!"]` (note that this must be on one line)
- bool: `true` and `false` (1 and 0)
- empty states: `nil` which is used for undefined values and `none` which is emptiness.


## Variables

Variables are easy!

```
import "text_io.py"

set this_var "to this string"
# or with fancy names! (as long as dots are used properly and no spaces!)
set name{this-works?} "what?"
object test
set test.this "Oh this is an attribute!"

io println %this_var %{this-works?} %test.this
```

## Functions

```
import "text_io.py"

fn greet name
	_global.io println (sum "Hello " %name "!")
end

fn name{can_return?}
	return "Wow!" 69
end

greet "You"
catch [return_value nice_value] name{can_return?}
io println %return_value %nice_value
```

## If statements

```
import "text_io.py"

io print "Name: "
io input name
if (%input caseless{==} admin)
	io println "Hello admin!"
end
```


### Using `if-then`

```
import "text_io.py"

io print "Name: "
io input name
if-then (%input caseless{==} admin)
	io println "Hello admin!"
then
	io println "Hello user!"
end
```

## Typed variables!

```
import "text_io.py"
import "typed_vars.py"

defv name %_mods.types.string
defv age %_mods.types.string

setv name "John Doe"
setv age 30

# An error will occur
setv age "30"
```

## Loops

```
import "text_io.py"

for name in [John Carl Jason]
	io println (sum "Hello " %name)
end

loop 10
	io println "Say this 10 times"
end

set count 100

while (%count > 0)
	io println %count
	set count (%count - 1)
end

loop
	io println "LOOP FOREVER THERE IS NO ESCAPE"
end
```

## Runtime info

```
import "text_io.py"

# Getting memory
pycatch [mem] _meta.internal.get_memory
# print a tuple (value, unit)
io println %mem

# Getting size of object
object really
pycatch [mem] _meta.internal.sizeof %really
# print a tuple (value, unit)
io println %mem
```

## Performance

Dont use it. If you do, please use Pypy3.
Performance on Python 3.13 is good.
But on Pypy its much more better!