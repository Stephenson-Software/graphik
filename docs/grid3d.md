# grid3d API reference

`preponderous.graphik.grid3d` draws a grid game's board in 3D with
[Strata](https://github.com/Preponderous-Software/strata). This page lists
every public name, grouped by what a game does with it, with a short example
for each group. The README's [3D grid view](../README.md#3d-grid-view-optional)
section is the tour; this is the reference.

Conventions used throughout:

- **World axes.** x runs along the columns, z along the rows (row 0 is the far
  edge, away from a camera south of the board), y is up. One cell is one world
  unit and a board is centred on the origin.
- **Colours.** Scene colours are 0-1 floats, `(r, g, b)` or `(r, g, b, a)`.
  The 2D stand-ins in `ui.py` (`Button`, `ScreenRecorder`) take 0-255
  colours, as `Graphik` does.
- **Screen units.** Labels, panels and pointers are in window pixels from the
  top-left (CSS pixels in a browser).
- **No GPU needed** for anything except `Grid3DView.open()`. Importing
  `grid3d` loads neither Strata nor pygame.

Contents: [Scene data](#scene-data) · [Boards and pieces](#boards-and-pieces) ·
[Animation](#animation) · [Picking and projection](#picking-and-projection) ·
[Text](#text) · [Buttons and 2D screens](#buttons-and-2d-screens) ·
[Touch keys](#touch-keys) ·
[The desktop view](#the-desktop-view) · [The browser view](#the-browser-view) ·
[The wire format](#the-wire-format) · [Fetching the relay](#fetching-the-relay) ·
[How the views are built](#how-the-views-are-built)

## Scene data

`scene.py`: a frame as plain data.

| Name | What it is |
|---|---|
| `CUBE`, `CAPSULE`, `CYLINDER`, `SPHERE` | Shape kinds 0-3, Strata's `STRATA_PRIMITIVE_*` |
| `Shape(kind, position, scale, color)` | An axis-aligned primitive; `scale` is its size along x, y, z |
| `Label(text, x, y, pixelSize, color=TEXT_COLOR)` | Screen text; `(x, y)` is the top-left of its first glyph |
| `Panel(x, y, width, height, color=(0, 0, 0, 0.6))` | A filled screen rectangle, drawn under every label |
| `Light(position, color, radius, intensity, castShadows=False)` | A point light. Strata takes a radius over 0 and no negative colour or intensity |
| `Camera(eye, target, fovDegrees=42.0)` | A right-handed look-at with +y up and a vertical field of view. It can't look straight up or down, or at its own eye |
| `Scene(shapes, labels, panels, lights, camera, clearColor)` | Everything one frame draws; `scene.checkLimits()` raises `SceneLimitError` |
| `SceneLimitError` | A `ValueError`: over `MAX_POINT_LIGHTS` (32) lights, over `MAX_SHADOWED_POINT_LIGHTS` (4) shadow casters, or an unknown shape kind |
| `TEXT_COLOR`, `DIM_TEXT_COLOR`, `CLEAR_COLOR` | Default colours |
| `rgb255(color)` | A 0-255 colour as 0-1 `(r, g, b)` |
| `rgba(color, alpha=1.0)` | `(r, g, b)` as `(r, g, b, alpha)` |
| `shade(color, factor)` | r, g and b scaled by `factor`, clamped to 0-1 |
| `fitText(text, width, pixelSize, margin=18)` | Text cut with `...` to fit `width` pixels (also in [Text](#text)) |

```python
from preponderous.graphik.grid3d import CUBE, Camera, Label, Light, Scene, Shape, rgb255, rgba

scene = Scene(camera=Camera(eye=(0, 8, 6), target=(0, 0, 0)))
scene.shapes.append(Shape(CUBE, (0, 0.25, 0), (1, 0.5, 1), rgba(rgb255((200, 60, 40)))))
scene.lights.append(Light((0, 2, 0), (1.0, 0.9, 0.7), radius=4.0, intensity=1.5))
scene.labels.append(Label("Hello", 16, 16, 24))
scene.checkLimits()
```

## Boards and pieces

`board.py`: what is on each cell, and how it looks.

| Name | What it is |
|---|---|
| `PieceStyle(kind, color, height, size, lift, glow, tones, extras)` | How one kind of piece looks. `glow=(radius, intensity)` adds a light above it; `tones=(odd, even)` shades a chain's links alternately; `extras(piece, x, z, baseY)` returns more `Shape`s placed relative to the piece |
| `Piece(id, column, row, style, scale, color, chain, link, facing, interpolate)` | Something on a cell. Keep `id` stable from tick to tick so it slides; `chain` and consecutive `link`s join orthogonal neighbours with a bridge; `interpolate=False` jumps |
| `Theme(tile, alternate, tileHeight, tileGap, frame, frameWidth, pieces, bridgeAcross, bridgeHeight, bridgeShade, highlight)` | The board's look; `pieces` maps a style name to a `PieceStyle`. `theme.style(name)` raises a `KeyError` naming the known styles |
| `Tile(color, raised=0.0)` | One cell's own tile (`GridBoard`'s `tiles`) |
| `Viewport(column, row, columns, rows)` | A window of a board; `Viewport.around(column, row, reach)` is the square around a cell; `contains(column, row)` |
| `GridBoard(columns, rows, theme=None, tiles=None, mergeTiles=False, viewport=None)` | A board drawn with a theme (below) |
| `cellCenter(column, row, columns, rows)` | World `(x, z)` of a cell's middle on a whole board |
| `fitCamera(columns, rows, aspect=1.0, fovDegrees=42.0, top=None, bottom=None)` | A camera south of the board that fits it in the window. A portrait window (aspect below 1) gets a steeper camera and a board that fills its width; between 0.8 and 1 the two framings blend. `top` and `bottom` are fractions of the window's height kept clear of the board (a HUD, a bar of touch keys) |
| `BED_TOP` | y of the tiles' top face (0.0); pieces stand on it |

`GridBoard` methods:

| Method | Returns |
|---|---|
| `scene(pieces, positions, labels, panels, lights, aspect, tint, clearColor, highlight, highlightColor, top, bottom)` | A complete `Scene`, lights checked; `highlight=(column, row)` lays a slab on that tile |
| `boardShapes(tint=None, tintAmount=0.55)` | The tiles and frame; `tint` blends every tile towards a colour |
| `pieceShapes(pieces, positions=None)` | `(shapes, lights)` for the pieces, at `positions` (id to world `(x, z)`) or on their cells |
| `highlightShapes(cell, color=None)` | The hover slab for one visible cell, or `[]` |
| `bridgePairs(pieces)`, `bridgeShape(a, b, aAt, bAt)` | The joined pairs of a chain in drawing order, and one bridge between two positions |
| `checkPieces(pieces)` | Raises `ValueError` (off the board, a duplicate id) or `KeyError` (unknown style) |
| `camera(aspect=1.0, top=None, bottom=None)` | `fitCamera` for what is on show |
| `cellCenter(column, row)`, `cellAt(x, z)` | Cell to world and back; `cellAt` is half-open (west and north edges in, east and south out) and `None` off the shown cells |
| `contains(column, row)`, `visible(column, row)` | On the board; on the board and in the viewport |
| `shownSize()`, `shownOrigin()` | The viewport's (or board's) size and top-left cell |
| `tileAt(column, row)`, `tileRaise(column, row)` | The `Tile` drawn on a cell (or `None` for a bare cell) and its raise |

```python
from preponderous.graphik.grid3d import SPHERE, CUBE, GridBoard, Piece, PieceStyle, Shape, Theme, Tile

def eyes(piece, x, z, baseY):  # placed from (x, z): they move with the piece
    return [Shape(SPHERE, (x + 0.2, baseY + 0.4, z - 0.3), (0.1, 0.1, 0.1), (1, 1, 1, 1))]

theme = Theme(pieces={
    "head": PieceStyle(SPHERE, (0.2, 0.8, 0.3), extras=eyes),
    "body": PieceStyle(CUBE, (0.1, 0.6, 0.2), tones=(0.9, 1.0)),
})
board = GridBoard(14, 10, theme, tiles={(3, 3): Tile((0.2, 0.4, 0.8), raised=0.05)}, mergeTiles=True)
snake = [Piece("s0", 5, 5, "head", chain="s", link=0), Piece("s1", 5, 6, "body", chain="s", link=1)]
scene = board.scene(snake, aspect=900 / 700, highlight=(5, 4))
```

## Animation

`animate.py`.

| Name | What it is |
|---|---|
| `Animator(cellCenter, reducedMotion=False, maxSlideCells=1.5)` | Slides each piece from where it was drawn to its new cell over one tick |
| `animator.update(pieces, now, tickSeconds, snap=False)` | Takes a tick's pieces at monotonic time `now`. A piece jumps when it is new, opted out, moved more than `maxSlideCells` (a diagonal step is 2), under reduced motion, or when `snap` is set. A tick of 0 or less (or NaN) places every piece at once |
| `animator.positions(now)` | id to world `(x, z)` at `now`; a time before the tick began gives its start |
| `animator.settled(now)` | True once every piece is on its cell |
| `animator.tracks` | id to `((x0, z0), (x1, z1))`, what the browser view sends |
| `interpolatePosition(start, end, alpha)` | `(x, z)` a fraction of the way, `alpha` clamped to 0-1 |

```python
import time
from preponderous.graphik.grid3d import Animator, GridBoard, Piece

board = GridBoard(8, 8)
animator = Animator(board.cellCenter)
animator.update([Piece(1, 0, 0, "pawn")], time.monotonic(), 0.15)
animator.update([Piece(1, 1, 0, "pawn")], time.monotonic(), 0.15)  # next tick
x, z = animator.positions(time.monotonic())[1]                     # somewhere between
```

## Picking and projection

`pick.py`: the same look-at and perspective the views ask Strata for.

| Name | Returns |
|---|---|
| `pickCell(camera, board, x, y, width, height)` | The `(column, row)` under window pixel `(x, y)`, gaps between tiles included, or `None` (off the board, out of the viewport, above the horizon, or `x`/`y` is `None`) |
| `pickPoint(camera, x, y, width, height, planeY=BED_TOP)` | World `(x, z)` where that pixel's ray meets the plane, or `None` |
| `screenRay(camera, x, y, width, height)` | The ray's direction (not normalised) |
| `projectToScreen(camera, point, width, height)` | Window `(x, y)` of a world point, or `None` behind the camera |
| `cellScreenPosition(camera, board, column, row, width, height, y=BED_TOP)` | Where a cell's middle lands, `y` above the bed |

A camera looking straight up or down, or with its eye on its target, raises
`ValueError`: Strata's look-at has no answer for those either, so tilt such a
camera a little. The views have the same calls bound to their own camera and
window: `view.camera()`, `view.pickCell(x, y)`, `view.projectToScreen(point)`,
`view.cellScreenPosition(column, row, y=0.0)`.

```python
from preponderous.graphik.grid3d import GridBoard, cellScreenPosition, pickCell

board = GridBoard(8, 8)
camera = board.camera(900 / 700)
cell = pickCell(camera, board, 450, 400, 900, 700)          # what was tapped
note = cellScreenPosition(camera, board, 2, 3, 900, 700)    # where to put a note
```

## Text

`text.py`: Strata's built-in font is 8 x 8 and monospaced: every character
is one `pixelSize`-wide cell. A character outside printable ASCII (an
accented letter, an emoji) is drawn as one `?`, still one cell, so text is
measured in characters, not bytes. A NUL draws nothing on either backend.

| Name | Returns |
|---|---|
| `measureText(text, pixelSize)` | The widest line's width in pixels |
| `fitText(text, width, pixelSize, margin=18)` | `text`, cut with `...` to fit |
| `wrapText(text, maxWidth, pixelSize)` | Lines, greedily word-wrapped; a word too long for a line stays whole on its own |
| `centredLabel(text, x, y, pixelSize, color=TEXT_COLOR, rise=0.5)` | A `Label` centred on `x`; `rise` places it on `y` (0.5 centres its cells, 0 puts its top there) |

```python
from preponderous.graphik.grid3d import centredLabel, wrapText

lines = wrapText("Eat the gems; avoid your own tail.", 300, 16)
labels = [centredLabel(line, 450, 200 + 20 * i, 16) for i, line in enumerate(lines)]
```

## Buttons and 2D screens

`ui.py`: menus over a 3D view that behave like `Graphik`'s. Colours are 0-255.

| Name | What it is |
|---|---|
| `Button(x, y, width, height, text, color, textColor, pixelSize=16, function=None, alpha=1.0, padding=None, rise=0.5)` | A screen button: `draw(pointer)` gives `(Panel, Label)` with the hover lift; `contains(position)` uses `drawButton`'s edges (left/top in, right/bottom out); `click(position)` runs `function`; `rect()` is the drawn box (widened by `padding` to fit its label) |
| `drawButtons(buttons, pointer=None)` | `([Label], [Panel])` for several buttons |
| `hoverColor(color)` | `drawButton`'s hover lift: light colours darken by 25, the rest lighten by 35 |
| `ScreenRecorder(width=800, height=600)` | Stands in for `Graphik` so a game's 2D screens run unchanged under a 3D view (below) |
| `RecordedText`, `RecordedRect`, `RecordedButton`, `RecordedImage` | What the recorder keeps for `drawText`, `drawRectangle`, `drawButton` and `drawImage` |
| `RecordedDisplay` | The recorder's `getGameDisplay()`: `get_size()`, `get_width()`, `get_height()`, `fill()` |

`ScreenRecorder` answers every public call and colour constant `Graphik`
has: `drawText`, `drawRectangle`, `drawButton`, `drawImage` (recorded),
`beginFrame` and `endFrame` (nothing to do: the 3D view sends a press to
`click()` itself, once), `getGameDisplay`, `getVersion`, and `black`,
`white`, `red`, `green`, `blue`. Then `items` is the frame's calls in order,
`texts()`, `buttons()` and `images()` pick them out, `click(position)` runs
the first recorded button under `position`, and `reset()` starts the next
frame, `resize(width, height)` follows the window.

```python
from preponderous.graphik.grid3d import Button, ScreenRecorder, drawButtons

play = Button(350, 300, 200, 48, "Play", color=(40, 120, 60), textColor=(255, 255, 255),
              pixelSize=20, function=lambda: print("play"), padding=12)
labels, panels = drawButtons([play], pointer=(400, 320))
play.click((400, 320))

recorder = ScreenRecorder(900, 700)
mainMenu.draw(recorder)        # a 2D screen that normally draws with Graphik
recorder.click((400, 320))     # runs that screen's own button function
```

## Touch keys

`touchkeys.py`: a bar of on-screen keys along the bottom of a touch screen,
drawn alike in 2D (with `Graphik`) and 3D (as HUD panels and labels) from one
layout and one hit test. Sizes are CSS pixels; `scale` is a surface's CSS
pixels per pixel (1 for the web view).

| Name | What it is |
|---|---|
| `TouchKey(label, key)` | One key: its label and the key it presses, by pygame's name (`"p"`, `"space"`, `"up"`, `"escape"`) |
| `TouchKeys(keys, minTarget=44, gap=6, margin=8, pixelSize=11, padding=6, portraitRows=3, landscapeRows=1, ...)` | The bar: rows of equal buttons, each at least `minTarget` each way. When the keys don't all fit, the last button is *More* (*Back* on the last page) |
| `keys.setKeys(keys)` | Changes the keys on offer (back to the first page) |
| `keys.layout(width, height, scale=1.0)` | The `KeySlot`s as laid out |
| `keys.bandHeight(width, height, scale=1.0)` | How much of the screen the bar takes, for `view.setInsets(bottom=...)` |
| `keys.below(width, height, pageWidth, pageHeight)` | The band a 2D game adds under its board, and the canvas's scale once the browser fits it to the page |
| `keys.press(position, width, height, pygame, scale=1.0)` | Posts the key's `KEYDOWN` and `KEYUP` (marked `touchKey=True`) and returns the `TouchKey`, `MORE` for More/Back, or `None` off the bar |
| `keys.draw(graphik, width, height, scale=1.0, pointer=None)` | Draws the bar in 2D |
| `keys.overlay(width, height, pointer=None)` | `(labels, panels)` for the 3D view's HUD |
| `keys.buttons(width, height)`, `keys.slotAt(position, width, height, scale=1.0)`, `TouchKeys.keyEvents(key, pygame)` | The bar as `Button`s (CSS pixels); the `KeySlot` under a point; the `KEYDOWN`/`KEYUP` pair a key posts |
| `KeySlot` | A laid-out button: `x`, `y`, `width`, `height`, `label`, `key`, `contains(position)` |
| `MIN_TARGET`, `MORE` | 44 (CSS pixels), and what `press()` returns for More |

```python
from preponderous.graphik.grid3d import TouchKey, TouchKeys
from preponderous.graphik.grid3d import web

keys = TouchKeys([TouchKey("Pause", "space"), TouchKey("Shop", "p")])
if web.touchScreen():
    view.setInsets(top=40, bottom=keys.bandHeight(390, 844))
    labels, panels = keys.overlay(390, 844)          # add to the HUD
    # on a tap:
    if keys.press(position, 390, 844, pygame) is None:
        handle(position)                              # not on the bar: the game's
```

## The desktop view

`view.py`. Linux and Windows x64; anywhere else `open()` raises
`Unavailable`.

| Name | What it is |
|---|---|
| `Grid3DView.open(width=900, height=700, title="graphik", headless=False, reducedMotion=False, clock=time.monotonic)` | A window, or a headless surface for tests and screenshots. Under pygbag it returns a `Grid3DWebView` instead |
| `view.setBoard(board, tint=None, lights=())` | The static part, when the board, theme or tint changes |
| `view.setPieces(pieces, tickSeconds=0.0, snap=False)` | Once per game tick |
| `view.setLabels(labels=(), panels=())` | When the HUD changes |
| `view.setInsets(top=None, bottom=None)` | Pixels at the top (a HUD) and bottom (touch keys) kept clear of the board; the camera, picking and `cellScreenPosition` follow. Returns whether anything changed |
| `view.frame(now=None, present=True)` | Draws one frame (pieces where they are at `now`) |
| `view.scene(now=None)` | The `Scene` that frame would draw |
| `view.drawScene(scene, present=True)` | Draws a `Scene` a game built itself |
| `view.pollEvents()` | Every pending Strata event (`view.EVENT_QUIT`, `EVENT_KEY_DOWN`, `EVENT_KEY_UP`, `EVENT_RESIZED`, ...) |
| `view.resize(width, height)`, `view.savePng(path)`, `view.close()` | |
| `view.setFullscreen(enabled)`, `view.setTitle(title)` | Desktop fullscreen on or off; the window's title. Each returns `False` when it can't: the loaded Strata lacks the call (0.8.0 has no `strata_set_title`), the view is closed, or (fullscreen) headless |
| `view.strata`, `view.lib`, `view.engine` | The binding, the loaded library and the engine, for calls graphik doesn't wrap. Prefer the view's own methods where there is one |
| `Grid3DView.using(display, width, height, isWindow=True, reducedMotion=False, clock=time.monotonic)` | A view drawing on any display that has the view's ports ([below](#how-the-views-are-built)): for tests and tools |
| `Unavailable` | Why 3D can't run here, in words a player can act on |
| `STRATA_VERSION` | The Strata release the binding loads (`STRATA_LIBRARY` points at a local build instead) |

```python
from preponderous.graphik.grid3d import Grid3DView, Unavailable

try:
    view = Grid3DView.open(900, 700, "My game")
except Unavailable as reason:
    view = None  # keep the 2D view, and say why
if view:
    view.setBoard(board)
    while running:
        for event in view.pollEvents():
            if event.type == view.EVENT_QUIT:
                running = False
        if tick():
            view.setPieces(pieces(), tickSeconds=0.15)
        view.frame()
    view.close()
```

## The browser view

`web.py`: under pygbag, the page's Strata grid relay draws what a desktop
view would. Build the page with `pygbag --template <templatePath()>` and copy
the relay next to it ([Fetching the relay](#fetching-the-relay)).

| Name | What it is |
|---|---|
| `Grid3DWebView` | `Grid3DView`'s calls (`setBoard`, `setPieces`, `setLabels`, `frame`, `scene`, `drawScene`, `pollEvents`, `resize`, `close`, picking) drawn by the relay. `frame()` does nothing: the page slides pieces itself. `drawScene()` sends only what changed. `savePng()` raises `Unavailable`; `setFullscreen()` and `setTitle()` return `False` (the browser owns its window, the page its title) |
| `Grid3DWebView.open(width, height, title, relay=None, maxBytes=4000000, reducedMotion=None, clock, canvas="relay")` | Asks the page for its 3D view; raises `Unavailable` when there is none or it failed |
| `view.ready`, `view.failure()` | Loaded yet; why it couldn't load |
| `templatePath(defaultView="3d")` | The pygbag page template, starting in 3D (or 2D) unless `?view=` or the player's last choice says otherwise |
| `wants3D()` | The page's 2D/3D button is on and the relay's scripts are in: time to `open()` |
| `set3D(on, reason="")` | Turns the button on or off; off with a reason marks 3D unavailable |
| `buttonArea()` | The button's `(x, y, width, height)` in CSS pixels, for keeping HUD text clear, or `None` |
| `touchScreen()` | The page is on a touch screen (a coarse pointer, or a touch seen; `?touch=1`/`?touch=0` overrides; `GRAPHIK_TOUCH=1` outside a browser): time to show `TouchKeys` |
| `parseArea(text)` | `"x,y,width,height"` as a tuple, or `None` |
| `pageObject(name)` | `window.<name>` under pygbag, or `None` |
| `toPygameEvents(events, pygame, keys=False, pointer=True, fingers=True)` | Relay (or desktop Strata) events as pygame events, so 2D input code runs unchanged. Keys are off by default: pygbag's SDL already gets them |
| `pygameKey(scancode, pygame)` | The pygame key for a USB HID scancode, or 0 |
| `Event` | A relay event: `type`, `scancode`, `modifiers`, `repeat`, `button`, `width`, `height`, `x`, `y`, `dx`, `dy`, `text`, `pointer`, `id`, `nx`, `ny`, `key`, `pressure` |
| `EVENTS`, `EVENT_*` | Event type numbers, Strata's and the web's `FINGER_*` |
| `PlatformRelay(relay=None, page=None)` | The transport to the page's `window.StrataGridRelay` (found through `page`, `PAGE` by default) |
| `PAGE` | Where the page helpers look for the page's objects (a `PageObjects`); a test can put a fake here |
| `RecordingRelay(reducedMotion=False, state="ready")` | A transport that keeps what it is sent: for tests, and `wireJson()` for the relay's test page |

```python
from preponderous.graphik.grid3d import Grid3DView, Unavailable
from preponderous.graphik.grid3d import web

view = None
def follow():  # call once per frame
    global view
    if web.wants3D() and view is None:
        try:
            view = Grid3DView.open(900, 700, "My game")   # a Grid3DWebView here
            view.setBoard(board)
        except Unavailable as reason:
            web.set3D(False, str(reason))
    elif not web.wants3D() and view is not None:
        view.close()
        view = None
    if view is not None:
        for event in web.toPygameEvents(view.pollEvents(), pygame):
            handle(event)   # the game's own 2D handler
```

The page goes back to 2D by itself, with the reason on screen, when 3D can't
start or when its drawing stays too slow once the game draws in it (for 5
seconds the typical frame and the kit's average frame are over 66 ms and the
relay's own drawing at least a quarter of the typical frame, with Strata's kit at its lowest tier and pixel density 1;
the game's own pauses don't count); the
latter is not remembered, the button brings 3D back, and `?slow=0` in the
address turns it off.

The button is a switch showing both views, *2D* and *3D*, with the one on
show lit: a toggle named "3D view", `aria-pressed` while 3D is on, at least
44 CSS pixels each way. `buttonArea()` measures it as drawn.

## The wire format

The messages `Grid3DWebView` sends, as functions: Strata's
`web/kit/grid-relay/WIRE.md` is the specification (format 1.0).

| Name | What it is |
|---|---|
| `encodeBoard(shapes, lights=())`, `encodePieces(board, pieces, tracks, tickSeconds)`, `encodeHud(labels=(), panels=())`, `encodeView(camera, clearColor, sun, near, far)` | One message each. They raise `WireError` for anything the relay would refuse, with the relay's status: counts over its limits (-6), and a non-finite number, a coordinate past ±10⁶, a light with no radius or a negative colour or intensity, a HUD colour with a negative part or alpha over 1, or a camera with its eye on its target (-5) |
| `decode(message)` | `(kind, contents)`, with the relay's checks: for tests and tools |
| `readHeader(message)` | `(major, minor, kind)`, or `WireError` as the relay says it |
| `header(kind)` | The 8-byte header |
| `WireError` | A `ValueError` with the relay's `status` (`STATUS` maps it to words) |
| `WIRE_MAJOR`, `WIRE_MINOR`, `MAGIC`, `BOARD`, `PIECES`, `HUD`, `VIEW`, `WORLD`, `PIECE`, `BRIDGE` | Format constants |
| `MAX_SHAPES`, `MAX_ANCHORS`, `MAX_LIGHTS`, `MAX_SHADOWED_LIGHTS`, `MAX_HUD_ITEMS`, `MAX_COORDINATE` | The relay's limits |
| `SUN_DIRECTION`, `NEAR_PLANE`, `FAR_PLANE` | The desktop view's, sent with every view |

The encoder is held to golden bytes
(`src/test/python/preponderous/graphik/grid3d/golden/wire-1.0.hex`) that
Strata's relay tests read with its own parser, so the two sides can't drift
apart unnoticed.

```python
from preponderous.graphik.grid3d import Label
from preponderous.graphik.grid3d import web

message = web.encodeHud([Label("Score 3", 12, 8, 16)])
kind, hud = web.decode(message)
assert kind == web.HUD and hud["labels"][0]["text"] == "Score 3"
```

## Fetching the relay

`relay.py`, run after `pygbag --build`:

```bash
python -m preponderous.graphik.grid3d.relay --strata 0.9.0 --dest build/web [--replace]
```

It downloads `strata-<version>-wasm32-emscripten.tar.gz` and the release's
`SHA256SUMS`, checks the tarball's SHA-256 (refusing a missing, malformed or
contradictory line), checks every member under `kit/grid-relay/dist/` before
writing anything (no links or devices, nothing outside `--dest`, even through
a link inside it, under 64 MB in all) and copies them next to the page. Files
already there are kept; with `--replace` the relay's own files are replaced
(after moving to a newer Strata) and only `index.html`, the game's page, is
kept. Only a release version (`0.9.0`, `1.0.0-rc.1`) is taken for `--strata`.

| Name | What it is |
|---|---|
| `fetchRelay(version, dest, base=RELEASES, download=None, replace=False)` | The whole fetch; returns `(copied, skipped)` |
| `extractDist(data, dest, prefix=DIST, replace=False)` | Unpacks a tarball's relay folder |
| `verify(data, sums, name)`, `expectedDigest(sums, name)` | The checksum check |
| `tarballName(version)` | The release asset's name |
| `RelayFetchError` | Why it couldn't fetch, verify or unpack |
| `main(argv=None)` | The command line |

## How the views are built

The two views share one core and differ only in what they draw on. Each
part of the outside world they touch sits behind a port (an interface, one
per file in `grid3d/ports/`), implemented by adapters (one per file in
`grid3d/adapters/`), and `view.py` and `web.py` wire the production
adapters in as defaults:

```
game -> Grid3DView (view.py)    -> ViewState, geometry, scene/board/animate/pick -> ports <- adapters
     -> Grid3DWebView (web.py)  -> ViewState, wire, events                       -> ports <- adapters
```

| Port | Question it answers | Adapters |
|---|---|---|
| `StrataLoader` | Can Strata run here? Open an engine | `BindingStrataLoader` (`view.STRATA_LOADER`) |
| `SceneRenderer` | Draw this Scene now | `StrataEngine`, `RelayDisplay` |
| `EventSource` | What input came since the last poll? | `StrataEngine`, `RelayDisplay` |
| `Surface` | Resize, snapshot, close | `StrataEngine`, `RelayDisplay` |
| `WindowChrome` | Fullscreen and the window's title | `StrataEngine`, `RelayDisplay` |
| `GridRelay` | Talk to the page's grid relay | `PlatformRelay`, `RecordingRelay` |
| `PageObjects` | Which of the page's JS objects exist? | `PygbagPageObjects` (`web.PAGE`) |

The model and core (`errors.py`, `geometry.py`, `state.py`, `wire.py`,
`events.py`, and the scene, board, animation, picking, text, button and
touch-key modules) import no adapter and no view; `test_grid3d_architecture.py`
fails if one does, or if a port or adapter file holds more than one class.
Every port has a contract test (`test_grid3d_ports.py`) that its fake and its
production adapters all pass. `grid3d.view` and `grid3d.web` still export
every name they did in 0.5.3.

To draw on something new (another engine, a recorder), write one adapter
file with the `SceneRenderer`, `EventSource`, `Surface` and `WindowChrome`
calls, add it to `adapters/__init__.py`, and hand it to
`Grid3DView.using(display, ...)`, or, for `open()`, add a `StrataLoader`
that returns it.
