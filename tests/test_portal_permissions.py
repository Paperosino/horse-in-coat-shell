"""Portal permission store and capability discovery on a private D-Bus."""
import ast,json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def mock():
 import dbus,dbus.service,dbus.mainloop.glib
 from gi.repository import GLib
 dbus.mainloop.glib.DBusGMainLoop(set_as_default=True);bus=dbus.SessionBus();names=[dbus.service.BusName(n,bus) for n in ['org.freedesktop.portal.Desktop','org.freedesktop.impl.portal.PermissionStore']]
 class Portal(dbus.service.Object):
  @dbus.service.method('org.freedesktop.portal.FileChooser')
  def Fixture(self):pass
 class Store(dbus.service.Object):
  values={}
  @dbus.service.method('org.freedesktop.impl.portal.PermissionStore',in_signature='sss',out_signature='as')
  def GetPermission(self,table,resource,app):
   key=(str(table),str(resource),str(app))
   if key not in self.values:raise dbus.exceptions.DBusException('No permission',name='org.freedesktop.portal.Error.NotFound')
   return self.values[key]
  @dbus.service.method('org.freedesktop.impl.portal.PermissionStore',in_signature='sbssas')
  def SetPermission(self,table,create,resource,app,permissions):self.values[(str(table),str(resource),str(app))]=list(permissions)
  @dbus.service.method('org.freedesktop.impl.portal.PermissionStore',in_signature='sss')
  def DeletePermission(self,table,resource,app):
   key=(str(table),str(resource),str(app))
   if key not in self.values:raise dbus.exceptions.DBusException('No permission',name='org.freedesktop.portal.Error.NotFound')
   del self.values[key]
 objects=[Portal(bus,'/org/freedesktop/portal/desktop'),Store(bus,'/org/freedesktop/impl/portal/PermissionStore')]
 print('ready',flush=True);GLib.MainLoop().run()
def fixture():
 with tempfile.TemporaryDirectory(prefix='hics-portals-') as tmp:
  base=Path(tmp);env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS=os.environ['DBUS_SESSION_BUS_ADDRESS'],XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),HOME=tmp)
  server=subprocess.Popen([sys.executable,__file__,'--mock'],env=env,stdout=subprocess.PIPE,text=True)
  daemon=None
  try:
   assert server.stdout.readline().strip()=='ready'
   daemon=subprocess.Popen([str(ROOT/'build/native/desktop/hics-desktopd')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   def call(method,*args):
    text=subprocess.check_output(['gdbus','call','--session','--dest','org.hics.Desktop1','--object-path','/org/hics/Desktop1','--method','org.hics.Desktop1.'+method,*args],env=env,text=True,stderr=subprocess.DEVNULL)
    return json.loads(ast.literal_eval(text)[0])
   for _ in range(100):
    try:call('Status');break
    except subprocess.CalledProcessError:time.sleep(.02)
   def job(op,**args):
    response=call('Start',op,json.dumps(args));assert 'id' in response,response
    for _ in range(200):
     value=call('Result',response['id'])
     if value.get('finished'):return value
     time.sleep(.02)
    raise AssertionError('Portal job timed out')
   app='org.hics.Fixture'
   status=job('apps.portal-status',id=app);assert not status['error'],status
   data=status['result'];assert data['available'] and any(c['id']=='FileChooser' and c['available'] for c in data['capabilities']),data
   for kind in ['camera','background','notifications']:
    assert not job('apps.portal-permission',id=app,kind=kind,policy='no')['error']
    assert job('apps.portal-status',id=app)['result']['permissions'][kind]['policy']=='no'
    assert not job('apps.portal-permission',id=app,kind=kind,policy='default')['error']
    assert job('apps.portal-status',id=app)['result']['permissions'][kind]['policy']=='default'
   assert job('apps.portal-permission',id=app,kind='arbitrary-table',policy='yes')['error']
   print('PORTAL_PERMISSIONS_OK',flush=True)
  finally:
   for proc in [daemon,server]:
    if proc and proc.poll() is None:proc.terminate();proc.wait(timeout=5)
class PortalTests(unittest.TestCase):
 def test_permission_roundtrip(self):
  result=subprocess.run(['dbus-run-session','--',sys.executable,__file__,'--fixture'],capture_output=True,text=True,timeout=30)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
if __name__=='__main__':
 if '--mock' in sys.argv:mock()
 elif '--fixture' in sys.argv:fixture()
 else:unittest.main()
