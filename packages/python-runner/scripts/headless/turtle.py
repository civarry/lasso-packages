"""A turtle that draws to a picture: Python's turtle needs a window, which Lasso's sandbox can't open.

Same names as the standard module for drawing (Turtle, Screen, forward, left, circle, color, begin_fill,
write, dot…). What needs a person at a window (keys, clicks, timers, animation) does nothing; the
picture is the drawing as it stands when the program ends, saved as drawing.png by /draw.
"""
import atexit, math, os

_COLORS = {
    "black": (0, 0, 0), "white": (1, 1, 1), "red": (1, 0, 0), "green": (0, .5, 0), "lime": (0, 1, 0), "blue": (0, 0, 1),
    "yellow": (1, 1, 0), "orange": (1, .65, 0), "purple": (.5, 0, .5), "violet": (.93, .51, .93), "pink": (1, .75, .8),
    "brown": (.65, .16, .16), "gray": (.5, .5, .5), "grey": (.5, .5, .5), "cyan": (0, 1, 1), "magenta": (1, 0, 1),
    "gold": (1, .84, 0), "navy": (0, 0, .5), "maroon": (.5, 0, 0), "olive": (.5, .5, 0), "teal": (0, .5, .5),
    "silver": (.75, .75, .75), "beige": (.96, .96, .86), "tan": (.82, .71, .55), "khaki": (.94, .9, .55),
    "salmon": (.98, .5, .45), "coral": (1, .5, .31), "tomato": (1, .39, .28), "crimson": (.86, .08, .24),
    "darkgreen": (0, .39, 0), "darkblue": (0, 0, .55), "darkred": (.55, 0, 0), "darkorange": (1, .55, 0),
    "lightblue": (.68, .85, .9), "lightgreen": (.56, .93, .56), "lightgray": (.83, .83, .83), "lightgrey": (.83, .83, .83),
    "lightyellow": (1, 1, .88), "skyblue": (.53, .81, .92), "forestgreen": (.13, .55, .13), "chocolate": (.82, .41, .12),
    "sienna": (.63, .32, .18), "wheat": (.96, .87, .7), "ivory": (1, 1, .94), "indigo": (.29, 0, .51),
    "turquoise": (.25, .88, .82), "darkgray": (.66, .66, .66), "darkgrey": (.66, .66, .66), "saddlebrown": (.55, .27, .07),
}
_mode = [1.0]

def _rgb(value, fallback=(0, 0, 0)):
    if isinstance(value, (tuple, list)) and len(value) == 3:
        scale = 255.0 if _mode[0] == 255 or any(v > 1 for v in value) else 1.0
        return tuple(max(0.0, min(1.0, float(v) / scale)) for v in value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v.startswith("#") and len(v) in (4, 7):
            v = "".join(c * 2 for c in v[1:]) if len(v) == 4 else v[1:]
            try:
                return tuple(int(v[i:i + 2], 16) / 255 for i in (0, 2, 4))
            except ValueError:
                return fallback
        return _COLORS.get(v.replace(" ", ""), fallback)
    return fallback

class _Canvas:
    def __init__(self):
        self.width, self.height = 800, 600
        self.background = (1, 1, 1)
        self.title = ""
        self.items = []

_canvas = _Canvas()

class Vec2D(tuple):
    def __new__(cls, x, y):
        return tuple.__new__(cls, (x, y))

class _Screen:
    def setup(self, width=None, height=None, startx=None, starty=None):
        if isinstance(width, int) and width > 50: _canvas.width = min(width, 2400)
        if isinstance(height, int) and height > 50: _canvas.height = min(height, 2400)
    def screensize(self, canvwidth=None, canvheight=None, bg=None):
        self.setup(canvwidth, canvheight)
        if bg: self.bgcolor(bg)
        return (_canvas.width, _canvas.height)
    def bgcolor(self, *args):
        if args: _canvas.background = _rgb(args[0] if len(args) == 1 else args, (1, 1, 1))
    def title(self, text=""): _canvas.title = str(text)
    def colormode(self, mode=None):
        if mode in (1.0, 255): _mode[0] = mode
        return _mode[0]
    def window_width(self): return _canvas.width
    def window_height(self): return _canvas.height
    def clear(self): _canvas.items.clear()
    def reset(self): _canvas.items.clear()
    # Things a person does at a window: nothing here.
    def tracer(self, *a, **k): pass
    def update(self): pass
    def delay(self, *a): pass
    def listen(self, *a): pass
    def onkey(self, *a, **k): pass
    onkeypress = onkeyrelease = onkey
    def onclick(self, *a, **k): pass
    onscreenclick = onclick
    def ontimer(self, *a, **k): pass
    def mainloop(self): pass
    done = exitonclick = bye = mainloop
    def register_shape(self, *a, **k): pass
    addshape = register_shape
    def textinput(self, *a, **k): return None
    def numinput(self, *a, **k): return None
    def turtles(self): return list(_turtles)
    def getcanvas(self): return None

_screen = _Screen()

def Screen():
    return _screen

_turtles = []

class Turtle:
    def __init__(self, shape="classic", undobuffersize=1000, visible=True):
        self._x = self._y = 0.0
        self._heading = 0.0
        self._down = True
        self._pen = (0, 0, 0)
        self._fill = (0, 0, 0)
        self._width = 1.0
        self._path = None
        self._filling = None
        _turtles.append(self)

    # Moving
    def _move(self, x, y):
        if self._down:
            if self._path is None:
                self._path = [(self._x, self._y)]
                _canvas.items.append(["line", self._path, self._pen, self._width])
            self._path.append((x, y))
        else:
            self._path = None
        if self._filling is not None:
            self._filling.append((x, y))
        self._x, self._y = float(x), float(y)

    def forward(self, distance):
        a = math.radians(self._heading)
        self._move(self._x + distance * math.cos(a), self._y + distance * math.sin(a))
    fd = forward
    def backward(self, distance): self.forward(-distance)
    bk = back = backward
    def left(self, angle): self._heading = (self._heading + angle) % 360
    lt = left
    def right(self, angle): self._heading = (self._heading - angle) % 360
    rt = right
    def goto(self, x, y=None):
        if y is None: x, y = x
        self._move(x, y)
    setpos = setposition = goto
    def setx(self, x): self._move(x, self._y)
    def sety(self, y): self._move(self._x, y)
    def setheading(self, angle): self._heading = angle % 360
    seth = setheading
    def home(self): self._move(0, 0); self._heading = 0.0
    def teleport(self, x=None, y=None, **k):
        self._path = None
        self._x = self._x if x is None else float(x)
        self._y = self._y if y is None else float(y)

    def circle(self, radius, extent=None, steps=None):
        extent = 360 if extent is None else extent
        steps = steps or max(12, int(abs(extent) / 6))
        step = extent / steps
        length = 2 * abs(radius) * math.sin(math.radians(abs(step)) / 2)
        turn = step if radius >= 0 else -step
        self.left(turn / 2)
        for _ in range(steps):
            self.forward(length)
            self.left(turn)
        self.left(-turn / 2)

    def dot(self, size=None, *color):
        size = size or max(self._width + 4, self._width * 2)
        c = _rgb(color[0] if len(color) == 1 else color, self._pen) if color else self._pen
        _canvas.items.append(["dot", (self._x, self._y), size, c])

    def stamp(self):
        _canvas.items.append(["dot", (self._x, self._y), 8, self._fill])
        return len(_canvas.items)

    # Pen
    def penup(self): self._down = False; self._path = None
    pu = up = penup
    def pendown(self): self._down = True
    pd = down = pendown
    def isdown(self): return self._down
    def pensize(self, width=None):
        if width is None: return self._width
        self._width = float(width); self._path = None
    width = pensize
    def pencolor(self, *args):
        if not args: return self._pen
        self._pen = _rgb(args[0] if len(args) == 1 else args, self._pen); self._path = None
    def fillcolor(self, *args):
        if not args: return self._fill
        self._fill = _rgb(args[0] if len(args) == 1 else args, self._fill)
    def color(self, *args):
        if not args: return self._pen, self._fill
        if len(args) == 2: self.pencolor(args[0]); self.fillcolor(args[1])
        elif len(args) == 3: self.pencolor(args); self.fillcolor(args)
        else: self.pencolor(args[0]); self.fillcolor(args[0])
    def begin_fill(self):
        self._filling = [(self._x, self._y)]
        self._fill_at = len(_canvas.items)
        self._path = None
    def end_fill(self):
        if self._filling and len(self._filling) > 2:
            # Under the outline drawn while filling, over everything drawn before it.
            _canvas.items.insert(self._fill_at, ["fill", list(self._filling), self._fill])
        self._filling = None
    def filling(self): return self._filling is not None

    def write(self, arg, move=False, align="left", font=("Arial", 8, "normal")):
        size = font[1] if isinstance(font, (tuple, list)) and len(font) > 1 else 8
        bold = isinstance(font, (tuple, list)) and len(font) > 2 and "bold" in str(font[2]).lower()
        _canvas.items.append(["text", (self._x, self._y), str(arg), align, float(size), self._pen, bold])

    # State
    def position(self): return Vec2D(self._x, self._y)
    pos = position
    def xcor(self): return self._x
    def ycor(self): return self._y
    def heading(self): return self._heading
    def distance(self, x, y=None):
        if y is None: x, y = x
        return math.hypot(x - self._x, y - self._y)
    def towards(self, x, y=None):
        if y is None: x, y = x
        return math.degrees(math.atan2(y - self._y, x - self._x)) % 360
    def clear(self): pass
    def reset(self): self.__init__()
    # How it looks and moves on screen: nothing to draw.
    def shape(self, *a, **k): return "classic"
    def shapesize(self, *a, **k): pass
    turtlesize = shapesize
    def speed(self, *a): return 0
    def hideturtle(self): pass
    ht = hideturtle
    def showturtle(self): pass
    st = showturtle
    def isvisible(self): return False
    def onclick(self, *a, **k): pass
    onrelease = ondrag = onclick
    def getscreen(self): return _screen
    def undo(self): pass

Pen = RawTurtle = Turtle

_default = []

def _turtle():
    if not _default:
        _default.append(Turtle())
    return _default[0]

for _name in ["forward", "fd", "backward", "bk", "back", "left", "lt", "right", "rt", "goto", "setpos", "setposition",
              "setx", "sety", "setheading", "seth", "home", "teleport", "circle", "dot", "stamp", "penup", "pu", "up",
              "pendown", "pd", "down", "isdown", "pensize", "width", "pencolor", "fillcolor", "color", "begin_fill",
              "end_fill", "filling", "write", "position", "pos", "xcor", "ycor", "heading", "distance", "towards",
              "shape", "shapesize", "turtlesize", "speed", "hideturtle", "ht", "showturtle", "st", "isvisible",
              "undo", "getscreen"]:
    globals()[_name] = (lambda n: lambda *a, **k: getattr(_turtle(), n)(*a, **k))(_name)
for _name in ["setup", "screensize", "bgcolor", "title", "colormode", "window_width", "window_height", "tracer",
              "update", "delay", "listen", "onkey", "onkeypress", "onkeyrelease", "onclick", "onscreenclick", "ontimer",
              "mainloop", "done", "exitonclick", "bye", "register_shape", "addshape", "textinput", "numinput"]:
    globals()[_name] = getattr(_screen, _name)

def clear(): _screen.clear()
def reset(): _screen.reset()

class Terminator(Exception):
    pass

# The picture

def _render(path):
    import _lassodraw
    _lassodraw.render(_canvas.items, _canvas.width, _canvas.height, _canvas.background, path + ".png")

@atexit.register
def _save():
    target = os.environ.get("LASSO_DRAWING")
    if target and _canvas.items:
        _render(target)
