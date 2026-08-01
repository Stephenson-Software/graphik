import pygame

from ._version import __version__


#  @author Daniel McCoy Stephenson
#  @since February 3rd, 2022
class Graphik:
    # Color constants, reachable as Graphik.white or instance.white, etc.
    black = (0, 0, 0)
    white = (255, 255, 255)
    red = (200, 0, 0)
    green = (0, 200, 0)
    blue = (0, 0, 200)

    def __init__(self, gameDisplay=None):
        # Consumers normally pass their own gameDisplay-backed surface. When
        # none is supplied, fall back to a default 900x600 window so the
        # no-argument Graphik() form works instead of raising.
        if gameDisplay is None:
            displayWidth = 900
            displayHeight = 600
            gameDisplay = pygame.display.set_mode((displayWidth, displayHeight))
        self.gameDisplay = gameDisplay
        # Fonts cached by size, plus the display surface they were built
        # against. See _getFont for why both are needed.
        self._fonts = {}
        self._fontDisplay = None
        # Images cached by file path: the loaded (unscaled) surface, plus the
        # most recent (size, scaled surface) pair. See drawImage for why this
        # doesn't need the font cache's session-invalidation logic.
        self._images = {}
        self._scaledImages = {}

    def getGameDisplay(self):
        return self.gameDisplay

    def getVersion(self):
        return __version__

    def drawRectangle(self, xpos, ypos, width, height, color):
        pygame.draw.rect(self.gameDisplay, color, [xpos, ypos, width, height])

    def _getFont(self, size):
        # Building a Font parses and rasterizes the TrueType file, which costs
        # far more than the render() it exists to serve, so keep one per size
        # instead of rebuilding it on every frame's drawText.
        if not pygame.font.get_init():
            # The constructor only sets up a display, so a consumer can reach
            # here having never initialized the font module; bring it up rather
            # than failing with a bare "font not initialized". Anything already
            # cached belongs to the previous font session (see below).
            pygame.font.init()
            self._fonts.clear()

        # A Font that outlives a font.quit()/init() cycle points at freed
        # SDL_ttf memory and segfaults when used, and pygame offers no way to
        # test a Font for validity. Restarting pygame drops the display
        # surface, so treat a change of that object as a new session and
        # rebuild. (A resize returns the same surface, so this does not
        # discard the cache on every set_mode.)
        #
        # Not covered: a consumer that calls pygame.font.quit() followed by
        # pygame.font.init() itself, leaving the display alone -- pygame
        # exposes nothing that distinguishes that from an untouched module.
        # Build a new Graphik after restarting the font module that way.
        display = pygame.display.get_surface()
        if display is not self._fontDisplay:
            self._fonts.clear()
            self._fontDisplay = display

        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font('freesansbold.ttf', size)
        return self._fonts[size]

    def drawText(self, text, xpos, ypos, size, color):
        myFont = self._getFont(size)
        textSurface = myFont.render(text, True, color)
        textRectangle = textSurface.get_rect()
        textRectangle.center = ((xpos, ypos))
        self.gameDisplay.blit(textSurface, textRectangle)

    def drawButton(self, xpos, ypos, width, height, colorBox, colorText, sizeText, text, function):
        # Polls the current mouse state rather than tracking press/release
        # edges, so function() fires on every call where the mouse is held
        # inside the button with button 1 down -- once per call, not once
        # per click. Deliberately left this way: the vendored copies in
        # Roam/Apex/Ophidian/Patchwork/Tic-Tak-Toe are written against this
        # repeat-fire behavior. Callers wanting once-per-click semantics
        # must debounce on their side.
        self.drawRectangle(xpos, ypos, width, height, colorBox)
        self.drawText(text, xpos + (width//2), ypos + (height//2), sizeText, colorText)
        
        # if clicked then do function
        mouse = pygame.mouse.get_pos()
        if (xpos + width > mouse[0] > xpos and ypos + height > mouse[1] > ypos):
            click = pygame.mouse.get_pressed()
            if click[0] == 1:
                function()

    def drawImage(self, filePath, xpos, ypos, width, height):
        # Loading decodes the file from disk and scaling resamples it, both of
        # which cost far more than the blit() they exist to serve, so cache
        # both by filePath instead of redoing them every call. Unlike
        # _getFont's Font objects, a surface from pygame.image.load survives a
        # pygame.quit()/init() cycle (verified empirically), so this cache
        # does not need the font cache's display-session invalidation.
        #
        # A failed load caches nothing, so a missing path keeps raising on
        # every call. Keying on path also means an asset edited on disk
        # mid-run will not be picked up -- the normal tradeoff for a game
        # asset cache.
        if filePath not in self._images:
            # convert_alpha() rebuilds the surface in the display's pixel
            # format (and preserves any per-pixel alpha), which is what makes
            # repeated blit() calls fast -- an unconverted surface is
            # reformatted on every single blit. Doing it once here, alongside
            # the load, keeps that cost out of the per-frame path this cache
            # exists to protect.
            self._images[filePath] = pygame.image.load(filePath).convert_alpha()
        image = self._images[filePath]

        size = (width, height)
        cachedSize, cachedScaled = self._scaledImages.get(filePath, (None, None))
        if cachedSize == size:
            scaledImage = cachedScaled
        else:
            scaledImage = pygame.transform.scale(image, size)
            self._scaledImages[filePath] = (size, scaledImage)

        self.gameDisplay.blit(scaledImage, (xpos, ypos))