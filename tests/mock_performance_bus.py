import dbus,dbus.service,os,json
from pathlib import Path
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
bus=dbus.bus.BusConnection(os.environ['DBUS_SESSION_BUS_ADDRESS'])
log=Path(os.environ['HICS_LEASE_TEST_LOG'])
def record(kind,**data):
 with log.open('a') as f:f.write(json.dumps(dict(kind=kind,**data))+'\n')
def pid(descriptor):
 fd=descriptor.take()
 try:
  row=next(x for x in Path(f'/proc/self/fdinfo/{fd}').read_text().splitlines() if x.startswith('Pid:'))
  return int(row.split(':')[1])
 finally:os.close(fd)
def defer(fn):
 delay=int(os.environ.get('HICS_LEASE_TEST_DELAY','0'))
 if delay:GLib.timeout_add(delay,lambda:(fn(),False)[1])
 else:fn()
class Game(dbus.service.Object):
 @dbus.service.method('com.feralinteractive.GameMode',in_signature='hh',out_signature='i',async_callbacks=('done','error'))
 def RegisterGameByPIDFd(self,game,caller,done,error):
  pids=[pid(game),pid(caller)]
  def finish():record('game-acquired',pids=pids);done(0)
  defer(finish)
 @dbus.service.method('com.feralinteractive.GameMode',in_signature='hh',out_signature='i')
 def UnregisterGameByPIDFd(self,game,caller):record('game-released',pids=[pid(game),pid(caller)]);return 0
class Power(dbus.service.Object):
 @dbus.service.method('org.freedesktop.UPower.PowerProfiles',in_signature='sss',out_signature='u',async_callbacks=('done','error'))
 def HoldProfile(self,profile,reason,application,done,error):
  def finish():record('power-acquired',profile=str(profile));done(dbus.UInt32(int(os.environ.get("HICS_LEASE_TEST_COOKIE","17"))))
  defer(finish)
 @dbus.service.method('org.freedesktop.UPower.PowerProfiles',in_signature='u',out_signature='')
 def ReleaseProfile(self,cookie):record('power-released',cookie=int(cookie))
game_name=dbus.service.BusName('com.feralinteractive.GameMode',bus)
power_name=dbus.service.BusName('org.freedesktop.UPower.PowerProfiles',bus)
game=Game(bus,'/com/feralinteractive/GameMode');power=Power(bus,'/org/freedesktop/UPower/PowerProfiles')
Path(os.environ['HICS_LEASE_TEST_READY']).touch();GLib.MainLoop().run()
