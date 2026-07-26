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
        self.drawRectangle(xpos, ypos, width, height, colorBox)
        self.drawText(text, xpos + (width//2), ypos + (height//2), sizeText, colorText)
        
        # if clicked then do function
        mouse = pygame.mouse.get_pos()
        if (xpos + width > mouse[0] > xpos and ypos + height > mouse[1] > ypos):
            click = pygame.mouse.get_pressed()
            if click[0] == 1:
                function()

    def drawImage(self, filePath, xpos, ypos, width, height):
        image = pygame.image.load(filePath)
        image = pygame.transform.scale(image, (width, height))
        self.gameDisplay.blit(image, (xpos, ypos))