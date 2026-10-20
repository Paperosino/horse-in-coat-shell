import os
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,Gdk,Gio
app=Gtk.Application(application_id='org.hyprstack.CanvasInputTest',flags=Gio.ApplicationFlags.NON_UNIQUE)
def activate(app):
 window=Gtk.ApplicationWindow(application=app,title='Canvas input regression');window.set_default_size(640,400)
 # Force client decorations/shadow margins: these exercise the bars motion
 # hook that must preserve the canvas's surface-local coordinates.
 window.set_titlebar(Gtk.HeaderBar())
 motion=Gtk.EventControllerMotion()
 motion.connect('motion',lambda controller,x,y:print('MOTION',round(x),round(y),window.get_width(),window.get_height(),flush=True))
 window.add_controller(motion)
 row=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,homogeneous=True)
 provider=Gtk.CssProvider();provider.load_from_string('.source {background:#00ee00;} .target {background:#ee0000;}')
 Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
 source=Gtk.Box();source.add_css_class('source');source.set_hexpand(True);source.set_vexpand(True)
 target=Gtk.Box();target.add_css_class('target');target.set_hexpand(True);target.set_vexpand(True)
 drag=Gtk.DragSource();drag.set_actions(Gdk.DragAction.COPY)
 def prepare(*args):print('PREPARE',flush=True);return Gdk.ContentProvider.new_for_value('hyprstack-test')
 drag.connect('prepare',prepare);source.add_controller(drag)
 drop=Gtk.DropTarget.new(str,Gdk.DragAction.COPY)
 def dropped(controller,value,x,y):print('DROP',value,round(x),round(y),flush=True);return True
 drop.connect('drop',dropped);target.add_controller(drop)
 middle=Gtk.GestureClick();middle.set_button(2)
 middle.connect('pressed',lambda *args:print('MIDDLE_PRESSED',flush=True))
 middle.connect('released',lambda *args:print('MIDDLE_RELEASED',flush=True));source.add_controller(middle)
 if os.environ.get('HYPRSTACK_ANIMATE'):
  area=Gtk.DrawingArea();area.set_size_request(24,24);target.append(area)
  counter=[0]
  def draw(widget,cr,width,height):
   cr.set_source_rgb(0,0,(counter[0]%120)/120);cr.paint()
  def tick(widget,clock):
   counter[0]+=1;widget.queue_draw()
   if counter[0]%60==0:print('FRAME',counter[0],flush=True)
   return True
  area.set_draw_func(draw);area.add_tick_callback(tick)
 row.append(source);row.append(target);window.set_child(row);window.present()
 if os.environ.get('HYPRSTACK_HIDE_CURSOR'):
  window.set_cursor_from_name('none')
app.connect('activate',activate);app.run([])
