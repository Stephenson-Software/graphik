import pygame

from ._version import __version__


#  @author Daniel McCoy Stephenson
#  @since February 3rd, 2022
class Graphik:
    """Helper methods for drawing to a pygame display surface.

    Every draw method renders to the surface the instance was constructed
    with, reachable through getGameDisplay(). Coordinates are in pixels and
    measured from the top-left of that surface, and colors are ``(r, g, b)``
    tuples -- the constants below cover the common cases.

    Anchoring is not uniform across the draw methods: drawRectangle,
    drawButton and drawImage position their top-left corner at the given
    ``(xpos, ypos)``, while drawText centers the rendered text on it.

    Example::

        import pygame
        from preponderous.graphik import Graphik

        pygame.init()
        graphik = Graphik(pygame.display.set_mode((900, 600)))
        graphik.drawRectangle(100, 100, 200, 50, Graphik.blue)
    """

    # Color constants, reachable as Graphik.white or instance.white, etc.
    black = (0, 0, 0)
    white = (255, 255, 255)
    red = (200, 0, 0)
    green = (0, 200, 0)
    blue = (0, 0, 200)

    def __init__(self, gameDisplay=None):
        """Bind a Graphik to the surface it draws on.

        Args:
            gameDisplay: The pygame surface every draw method renders to,
                normally the one returned by ``pygame.display.set_mode``.
                When omitted, a default 900x600 display is created, which
                opens a window as a side effect.
        """
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
        """Return the pygame surface this instance draws to."""
        return self.gameDisplay

    def getVersion(self):
        """Return the installed graphik version string.

        This is the same value as ``preponderous.graphik.__version__``, which
        is reachable without constructing a Graphik (and so without a display).
        """
        return __version__

    def drawRectangle(self, xpos, ypos, width, height, color):
        """Fill a rectangle on the display.

        Args:
            xpos: X coordinate of the rectangle's left edge, in pixels.
            ypos: Y coordinate of the rectangle's top edge, in pixels.
            width: Width of the rectangle, in pixels.
            height: Height of the rectangle, in pixels.
            color: Fill color as an ``(r, g, b)`` tuple.
        """
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
        """Render a line of text, centered on the given position.

        Note that ``(xpos, ypos)`` is the *center* of the rendered text, not
        its top-left corner as in drawRectangle, drawButton and drawImage.

        Args:
            text: The string to render.
            xpos: X coordinate the text is centered on, in pixels.
            ypos: Y coordinate the text is centered on, in pixels.
            size: Font size in points. The font module is initialized on
                demand, and one font per distinct size is cached and reused.
            color: Text color as an ``(r, g, b)`` tuple.
        """
        myFont = self._getFont(size)
        textSurface = myFont.render(text, True, color)
        textRectangle = textSurface.get_rect()
        textRectangle.center = ((xpos, ypos))
        self.gameDisplay.blit(textSurface, textRectangle)

    def drawButton(self, xpos, ypos, width, height, colorBox, colorText, sizeText, text, function):
        """Draw a labelled box and call ``function`` while it is being clicked.

        ``function()`` is called on every invocation where the mouse sits
        inside the box with button 1 held down -- once per call, not once per
        click. A caller wanting once-per-click semantics must debounce on its
        own side; see the implementation note below for why.

        The clickable region is exactly the region the box is drawn over:
        ``xpos`` through ``xpos + width - 1`` horizontally, and ``ypos``
        through ``ypos + height - 1`` vertically. Buttons laid out edge to
        edge therefore share no clickable coordinate -- a boundary belongs to
        the button whose left/top edge sits on it.

        Args:
            xpos: X coordinate of the box's left edge, in pixels.
            ypos: Y coordinate of the box's top edge, in pixels.
            width: Width of the box, in pixels.
            height: Height of the box, in pixels.
            colorBox: Fill color of the box as an ``(r, g, b)`` tuple.
            colorText: Color of the label as an ``(r, g, b)`` tuple.
            sizeText: Font size of the label, in points.
            text: The label, centered within the box.
            function: Zero-argument callable invoked as described above.
        """
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
        # Half-open on both axes, matching the range pygame.draw.rect fills, so
        # the clickable region is exactly the drawn one. A strict `> xpos` here
        # would leave the painted left and top edge columns unclickable, and a
        # closed `<= xpos + width` would let edge-to-edge buttons both claim
        # their shared boundary.
        if (xpos <= mouse[0] < xpos + width and ypos <= mouse[1] < ypos + height):
            click = pygame.mouse.get_pressed()
            if click[0] == 1:
                function()

    def drawImage(self, filePath, xpos, ypos, width, height):
        """Draw an image file, scaled to the given size.

        The loaded and scaled surfaces are cached against ``filePath``, so an
        asset edited on disk mid-run is not picked up until the process
        restarts. A path that fails to load caches nothing and raises on every
        call.

        Only the most recently requested size is kept per path: drawing the
        same file at a different size rescales it and replaces the cached
        scale, so alternating between two sizes rescales on every call.

        Args:
            filePath: Path to the image file, used as the cache key.
            xpos: X coordinate of the image's left edge, in pixels.
            ypos: Y coordinate of the image's top edge, in pixels.
            width: Width to scale the image to, in pixels.
            height: Height to scale the image to, in pixels.

        Raises:
            FileNotFoundError: If no file exists at ``filePath``.
            pygame.error: If the file exists but pygame cannot decode it.
        """
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