"""Display safety transactions, identity matching and atomic persistence."""
import copy,importlib,json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shell/assets'))
import display_profiles as displays

def monitor(name='DP-3',serial='unique',x=0):
 return dict(name=name,make='Maker',model='Panel',serial=serial,description='Panel '+serial,width=1920,height=1080,refreshRate=164.998,x=x,y=0,scale=1,transform=0,disabled=False,vrr=False,availableModes=['1920x1080@165.00Hz','1920x1080@60.00Hz'])
class DisplayProfiles(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
  self.registry=self.folder/'profiles.json';self.config=self.folder/'monitors.lua';self.live=[monitor()];self.applied=[]
  for p in (patch.object(displays,'REGISTRY',self.registry),patch.object(displays,'MONITOR_CONFIG',self.config),patch.object(displays,'connected',lambda:copy.deepcopy(self.live)),patch.object(displays,'apply_outputs',self.apply)):
   p.start();self.addCleanup(p.stop)
  self.manager=displays.Manager(self.folder)
 def apply(self,rows):
  self.applied.append(copy.deepcopy(rows))
  for row in rows:
   m=next(m for m in self.live if m['name']==row['name']);m.update({k:v for k,v in row.items() if k not in ('mode','name')})
   if row.get('mode')!='preferred':
    size,rate=row['mode'].split('@');m['width'],m['height']=map(int,size.split('x'));m['refreshRate']=float(rate)
 def dispatch(self,op,value=None):return self.manager.dispatch({'operation':op,'value':value})
 def preview(self):return self.dispatch('preview',{'patches':{'DP-3':{'mode':'1920x1080@60'}}})
 def test_preview_does_not_write_config_and_revert_restores_165hz(self):
  self.config.write_text('-- user content\n');before=self.config.read_bytes();state=self.preview()
  self.assertAlmostEqual(self.live[0]['refreshRate'],60);self.assertEqual(self.config.read_bytes(),before)
  self.dispatch('revert',{'token':state['pending']['token']});self.assertAlmostEqual(self.live[0]['refreshRate'],164.998);self.assertEqual(self.config.read_bytes(),before)
 def test_confirmation_commits_only_managed_block(self):
  self.config.write_text('-- before\n'+displays.START+'\nhl.monitor({})\n'+displays.END+'\n-- after\n')
  state=self.preview();self.dispatch('confirm',{'token':state['pending']['token']});text=self.config.read_text()
  self.assertTrue(text.startswith('-- before\n'));self.assertTrue(text.endswith('-- after\n'));self.assertEqual(text.count(displays.START),1);self.assertIn('1920x1080@60',text);self.assertFalse((self.folder/'pending.json').exists())
 def test_stale_token_and_concurrent_preview_are_rejected(self):
  state=self.preview()
  with self.assertRaises(ValueError):self.dispatch('confirm',{'token':'old'})
  with self.assertRaises(ValueError):self.preview()
  self.assertEqual(self.manager.pending['token'],state['pending']['token'])
 def test_expired_confirmation_reverts(self):
  state=self.preview();self.manager.deadline=time.monotonic()-1
  with self.assertRaises(ValueError):self.dispatch('confirm',{'token':state['pending']['token']})
  self.assertIsNone(self.manager.pending);self.assertAlmostEqual(self.live[0]['refreshRate'],164.998)
 def test_service_restart_recovers_the_journal(self):
  self.preview();self.assertEqual(self.live[0]['refreshRate'],60)
  recovered=displays.Manager(self.folder);self.assertIsNone(recovered.pending);self.assertAlmostEqual(self.live[0]['refreshRate'],164.998)
 def test_external_config_edit_is_never_overwritten(self):
  state=self.preview();self.config.write_text('-- edited elsewhere\n')
  with self.assertRaises(ValueError):self.dispatch('confirm',{'token':state['pending']['token']})
  self.assertEqual(self.config.read_text(),'-- edited elsewhere\n');self.assertAlmostEqual(self.live[0]['refreshRate'],164.998)
 def test_disconnected_output_cancels_confirmation(self):
  state=self.preview();self.live=[monitor('HDMI-A-1','new')]
  with self.assertRaises(ValueError):self.dispatch('confirm',{'token':state['pending']['token']})
  self.assertIsNone(self.manager.pending);self.assertFalse(self.config.exists())
 def test_identity_survives_connector_change_and_ports_can_be_strict(self):
  profile={'devices':[monitor()], 'outputs':displays.capture([monitor()])}
  current=[monitor('DP-7')]
  self.assertEqual(displays.map_outputs(profile,current)[0]['name'],'DP-7')
  with self.assertRaises(ValueError):displays.map_outputs(profile,current,True)
 def test_same_topology_prefers_the_selected_profile_and_does_not_repeat(self):
  first=self.dispatch('save',{'name':'Home'})['profiles'][0]
  self.preview();token=self.manager.pending['token'];self.dispatch('confirm',{'token':token})
  second=self.dispatch('save',{'name':'Dock'})['profiles'][1]
  self.dispatch('update',{'id':first['id'],'changes':{'preferred':True}})
  self.manager.monitors=copy.deepcopy(self.live);self.manager.attempt="";self.manager.automatic()
  self.assertEqual(self.manager.pending['profileId'],first['id']);self.assertTrue(self.manager.pending['automatic'])
  self.manager.rollback();self.manager.automatic();self.assertIsNone(self.manager.pending)
  self.assertNotEqual(first['id'],second['id'])
 def test_unknown_or_unsupported_input_never_reaches_compositor(self):
  for patch in ({'mode':'9999x9999@999'},{'scale':float('nan')},{'scale':1.4},{'x':True},{'disabled':True},{'mode':'preferred; os.execute("x")'}):
   with self.assertRaises(ValueError):self.dispatch('preview',{'patches':{'DP-3':patch}})
  self.assertFalse(self.applied);self.assertFalse(self.config.exists())
 def test_no_overlapping_displays_and_no_disabling_every_output(self):
  self.live.append(monitor('DP-4','second',1920));rows=displays.capture(self.live);rows[1]['x']=0
  with self.assertRaises(ValueError):displays.validate(rows,self.live)
  for row in rows:row['disabled']=True
  with self.assertRaises(ValueError):displays.validate(rows,self.live)
 def test_unapplied_preview_cannot_be_committed(self):
  state=self.preview();self.live[0]['refreshRate']=164.998
  with self.assertRaises(ValueError):self.dispatch('confirm',{'token':state['pending']['token']})
  self.assertFalse(self.config.exists())
if __name__=='__main__':unittest.main()
