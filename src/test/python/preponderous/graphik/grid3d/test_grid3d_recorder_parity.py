"""ScreenRecorder answers every call and constant Graphik has, so a 2D
screen written against Graphik 0.3.0 and later runs under a 3D view."""

import inspect

from preponderous.graphik import Graphik, __version__
from preponderous.graphik.grid3d import ScreenRecorder

# -- ScreenRecorder stands in for every call Graphik has


def test_the_recorder_answers_every_public_call_and_constant_graphik_has():
    public = [name for name, _ in inspect.getmembers(Graphik) if not name.startswith("_")]
    missing = [name for name in public if not hasattr(ScreenRecorder, name)]
    assert missing == []
    for name in public:
        value = getattr(Graphik, name)
        if not callable(value):
            assert getattr(ScreenRecorder, name) == value, name


def test_a_screen_using_press_only_clicks_and_images_runs_under_the_recorder():
    recorder = ScreenRecorder(400, 300)
    clicked = []

    def screen(graphik):  # a 2D screen written against Graphik 0.3.0
        graphik.beginFrame()
        graphik.drawImage("logo.png", 10, 10, 64, 64)
        graphik.drawButton(100, 100, 80, 30, graphik.blue, graphik.white, 20, "Play", lambda: clicked.append(1))
        graphik.endFrame()

    screen(recorder)
    assert [type(item).__name__ for item in recorder.items] == ["RecordedImage", "RecordedButton"]
    assert recorder.images()[0].filePath == "logo.png"
    assert recorder.click((120, 110)) and clicked == [1]
    assert recorder.getVersion() == __version__
