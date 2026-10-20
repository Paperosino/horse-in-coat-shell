import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Gio
import os, sys

MARGIN = int(os.environ.get('EDGE_MARGIN', '6'))

app = Gtk.Application(application_id='org.hyprstack.EdgeResizeTest', flags=Gio.ApplicationFlags.NON_UNIQUE)

def activate(app):
    window = Gtk.ApplicationWindow(application=app, title='Edge resize test')
    window.set_default_size(640, 400)
    box = Gtk.Box()
    box.set_size_request(640, 400)
    window.set_child(box)

    click = Gtk.GestureClick()
    def pressed(g, n, x, y):
        w = 640; h = 400
        edge = None
        if x < MARGIN: edge = Gdk.SurfaceEdge.WEST
        elif x >= w - MARGIN: edge = Gdk.SurfaceEdge.EAST
        elif y < MARGIN: edge = Gdk.SurfaceEdge.NORTH
        elif y >= h - MARGIN: edge = Gdk.SurfaceEdge.SOUTH
        elif x < MARGIN * 2 and y < MARGIN * 2: edge = Gdk.SurfaceEdge.NORTH_WEST
        toplevel = window.get_surface()
        device = g.get_device()
        if edge is not None and toplevel is not None:
            print(f'RESIZE_REQUEST edge={edge} at ({x},{y})', flush=True)
            toplevel.begin_resize(edge, device, 1, x, y, Gdk.CURRENT_TIME)
        else:
            print(f'NO_REQUEST at ({x},{y})', flush=True)
    click.connect('pressed', pressed)
    window.add_controller(click)
    window.present()

app.connect('activate', activate)
app.run([])
