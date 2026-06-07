import os

# Graphik draws through pygame, which needs a video (and sometimes audio) device.
# Force the headless SDL drivers so the suite runs without a real display.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
