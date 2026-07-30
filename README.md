# Graphik
This library assists developers with graphics programming.

## Installation
```bash
pip install graphik
```

## Usage
```python
import pygame
from preponderous.graphik import Graphik

pygame.init()
gameDisplay = pygame.display.set_mode((900, 600))
graphik = Graphik(gameDisplay)

graphik.drawRectangle(100, 100, 200, 50, Graphik.blue)
graphik.drawText("Hello, world!", 200, 125, 24, Graphik.white)
graphik.drawButton(100, 200, 200, 50, Graphik.green, Graphik.black, 24, "Click me", lambda: print("clicked"))
graphik.drawImage("path/to/image.png", 100, 300, 200, 200)
```

Public `Graphik` methods:
- `Graphik(gameDisplay=None)` — construct a helper bound to a pygame display surface (creates a default 900x600 window if none is given).
- `getGameDisplay()` — returns the bound display surface.
- `getVersion()` — returns the installed graphik version string.
- `drawRectangle(xpos, ypos, width, height, color)`
- `drawText(text, xpos, ypos, size, color)`
- `drawButton(xpos, ypos, width, height, colorBox, colorText, sizeText, text, function)` — draws a rectangle and centered text, and calls `function()` on every call where the mouse is held inside the button with button 1 down (there is no click-edge detection, so a held-down mouse fires `function()` once per call, not once per click). Callers wanting once-per-click semantics must debounce on their side.
- `drawImage(filePath, xpos, ypos, width, height)` — caches the loaded and scaled surface by `filePath`, so an image edited on disk mid-run will not be picked up until the process restarts.

Color constants: `Graphik.black`, `Graphik.white`, `Graphik.red`, `Graphik.green`, `Graphik.blue`.

## Dependencies
- pygame

## Development
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
pytest
```
The suite is headless: `src/test/python/conftest.py` sets `SDL_VIDEODRIVER`/`SDL_AUDIODRIVER` to `dummy` before pygame touches a display, so no window is created and the tests run on a machine with no display attached. `pytest` alone works from the repo root because `[tool.pytest.ini_options]` in `pyproject.toml` points `testpaths` at `src/test/python` and `pythonpath` at `src/main/python`. `.github/workflows/test.yml` runs the same `pip install -e ".[test]"` + `pytest` sequence on every push and pull request.

## Projects
[Projects that utilize this library](https://github.com/Stephenson-Software/graphik/wiki/Projects)

## 📄 License

graphik is licensed under the [MIT License](LICENSE).

Copyright © 2022–2025 Daniel McCoy Stephenson. All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software 
and associated documentation files (the “Software”), to deal in the Software without restriction, 
including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, 
and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, 
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies 
or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT 
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. 
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE 
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

### Why MIT?
The **MIT License** offers maximum freedom for developers to integrate **graphik** into their projects, whether for games, simulation tools, or research applications. This permissive approach is intended to boost adoption, encourage experimentation, and position **graphik** as a widely used rendering and visualization library.

### Open Source Commitment
There are **no plans to move away from open source** for **graphik**. The project will remain freely available under an OSI-approved license, with active encouragement for community use and contributions.
