"""Exercise the actual desktop daemon in an isolated session bus and home."""
import ast
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]

class DesktopServiceTest(unittest.TestCase):
    def test_service_exits_with_session_bus(self):
        with tempfile.TemporaryDirectory(prefix='hics-disconnected-bus-') as directory:
            bus = subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
            daemon = None
            try:
                env = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=bus.stdout.readline().strip(), XDG_STATE_HOME=directory)
                daemon = subprocess.Popen([os.environ.get('HICS_TEST_DESKTOP_DAEMON',str(ROOT/'build/native/desktop/hics-desktopd'))],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                for _ in range(60):
                    result=subprocess.run(['gdbus','call','--session','--dest','org.hics.Desktop1','--object-path','/org/hics/Desktop1','--method','org.hics.Desktop1.Status'],env=env,capture_output=True)
                    if not result.returncode: break
                    time.sleep(.05)
                self.assertEqual(result.returncode,0)
                bus.terminate(); bus.wait(timeout=3)
                self.assertEqual(daemon.wait(timeout=5),0)
            finally:
                if daemon and daemon.poll() is None: daemon.terminate(); daemon.wait(timeout=5)
                if bus.poll() is None: bus.terminate(); bus.wait(timeout=3)
                bus.stdout.close()

    def test_private_session(self):
        result = subprocess.run(['dbus-run-session', '--', 'python3', str(Path(__file__).resolve()), '--fixture'], capture_output=True, text=True, timeout=40)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('DESKTOP_SERVICE_OK', result.stdout)

def fixture():
    with tempfile.TemporaryDirectory(prefix='hics-desktop-test-') as temporary:
        base = Path(temporary)
        env = dict(os.environ, XDG_STATE_HOME=str(base/'state'), XDG_CONFIG_HOME=str(base/'config'), XDG_DATA_HOME=str(base/'data'), HOME=str(base/'home'))
        runtime=base/'runtime';runtime.mkdir(mode=0o700);env['XDG_RUNTIME_DIR']=str(runtime);env['GIO_USE_VFS']='local'
        home=base/'home'; home.mkdir()
        docs=home/'Documents'; docs.mkdir()
        (docs/'public.txt').write_text('public searchable orchard')
        private=docs/'private'; private.mkdir(); (private/'secret.txt').write_text('ultrasecret sentinel')
        hidden=docs/'.hidden'; hidden.mkdir(); (hidden/'hidden.txt').write_text('hidden sentinel')
        outside=base/'outside'; outside.mkdir(); (outside/'outside.txt').write_text('outside sentinel')
        (docs/'link').symlink_to(outside, target_is_directory=True)
        applications=base/'data/applications';applications.mkdir(parents=True)
        spy=base/'launch.py';spy.write_text('import json,sys,os\nwith open(os.environ["HICS_LAUNCH_TRACE"],"a") as target:target.write(json.dumps(sys.argv[1:])+"\\n")\n')
        env['HICS_LAUNCH_TRACE']=str(base/'launch.jsonl');env['HICS_FM_TRACE']=str(base/'reveal.json')
        for ident,name in [('org.gnome.Nautilus','Fixture Nautilus'),('org.kde.dolphin','Fixture Dolphin'),('org.gnome.FileRoller','Fixture Archiver')]:
            (applications/(ident+'.desktop')).write_text('[Desktop Entry]\nType=Application\nName='+name+'\nExec=/usr/bin/python3 '+str(spy)+' '+ident+' %U\nMimeType=inode/directory;application/zip;\n')
        config=base/'config';config.mkdir()
        mimeapps=config/'mimeapps.list';original='[Default Applications]\ninode/directory=org.gnome.Nautilus.desktop;\n'
        mimeapps.write_text(original)
        env['XDG_CURRENT_DESKTOP']='HicsFixture'
        mock = subprocess.Popen(['python3',str(ROOT/'tests/mock_desktop_jobs_bus.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        assert mock.stdout.readline().strip()=='ready'
        daemon = subprocess.Popen([os.environ.get('HICS_TEST_DESKTOP_DAEMON',str(ROOT/'build/native/desktop/hics-desktopd'))], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def call(method, *args):
            output=subprocess.check_output(['gdbus','call','--session','--dest','org.hics.Desktop1','--object-path','/org/hics/Desktop1','--method','org.hics.Desktop1.'+method,*args],text=True,stderr=subprocess.DEVNULL)
            return json.loads(ast.literal_eval(output)[0])
        def job(op, **args):
            response=call('Start',op,json.dumps(args)); assert 'id' in response,response
            for _ in range(150):
                value=call('Result',response['id'])
                if value.get('finished'):return value
                time.sleep(.02)
            raise AssertionError('job timeout '+op)
        try:
            for _ in range(60):
                try:call('Status');break
                except subprocess.CalledProcessError:time.sleep(.05)
            integration=job('integration.status')['result']
            assert any(row['id']=='org.kde.dolphin.desktop' for row in integration['managers']),integration
            assert not job('integration.prefer',kind='manager',id='org.kde.dolphin.desktop')['error']
            assert 'org.kde.dolphin.desktop' in mimeapps.read_text()
            assert not job('integration.undo')['error']
            assert mimeapps.read_text()==original,mimeapps.read_text()
            assert not job('integration.prefer',kind='archiver',id='org.gnome.FileRoller.desktop')['error']
            mimeapps.write_text(mimeapps.read_text()+'# external edit\n')
            assert job('integration.undo')['error'] and mimeapps.read_text().endswith('# external edit\n')
            assert job('integration.prefer',kind='manager',id='injected.desktop')['error']
            assert not job('integration.open',target='home')['error']
            import zipfile
            archive=base/'test archive.zip'
            with zipfile.ZipFile(archive,'w') as output:output.writestr('hello.txt','fixture')
            assert not job('integration.open',target='archive',path=str(archive))['error']
            for _ in range(50):
                if (base/'launch.jsonl').exists() and len((base/'launch.jsonl').read_text().splitlines())>=2:break
                time.sleep(.02)
            launches=[json.loads(line) for line in (base/'launch.jsonl').read_text().splitlines()]
            assert any(row[0]=='org.gnome.Nautilus' for row in launches),launches
            assert any(row[0]=='org.gnome.FileRoller' for row in launches),launches
            assert not job('integration.reveal',path=str(archive))['error']
            assert json.loads((base/'reveal.json').read_text())==[archive.as_uri()]

            assert not job('comfort.focus-start',minutes=25,quiet=True)['error']
            assert call('Status')['comfort']['focus']['phase']=='work'
            assert not job('comfort.focus-options',quiet=False,keepAwake=True)['error']
            assert call('Status')['comfort']['focus']['quiet'] is False
            assert not job('comfort.focus-pause')['error']
            assert call('Status')['comfort']['focus']['paused']
            assert not job('comfort.focus-resume')['error']
            assert not job('comfort.awake',minutes=30)['error']
            assert job('comfort.awake',minutes=-1)['error']
            result=job('search.configure',folders=[str(docs)],excluded=[str(private)],contents=True,maxFiles=100)
            assert not result['error'], result
            result=job('search.index');assert result['result']['count']==1,result
            result=job('search.query',query='orchard');assert result['result']['items'][0]['path']==str(docs/'public.txt'),result
            for word in ['sentinel','secret','outside','hidden']:
                result=job('search.query',query=word);assert result['result']['items']==[],result
            result=job('search.configure',excluded=[str(docs)])
            assert not job('search.query',query='orchard')['result']['items']
            result=job('apps.flatpak-reset',id='--system');assert result['error'],result
            result=job('backup.restore',snapshot='latest',target='/');assert result['error'],result
            output=job('input.symbols',query='U+1F600');assert output['result']['items'][0]['text']=='😀',output
            status=job('input.status');assert status['result']['running'] and len(status['result']['methods'])==2,status
            assert not job('input.group-create',group='Russian')['error']
            assert not job('input.group-save',group='Russian',layout='ru',entries=[{'id':'keyboard-ru','layout':''}])['error']
            assert not job('input.group-activate',group='Russian')['error']
            status=job('input.status');assert status['result']['currentGroup']=='Russian' and status['result']['entries'][0]['id']=='keyboard-ru',status
            assert job('input.group-save',group='Russian',entries=[{'id':'injected','layout':''}])['error']
            assert not job('input.osk',visible=True)['error']
            assert not job('apps.portal-camera',id='org.example.App',policy='no')['error']
            desktop=base/'autostart.desktop';desktop.write_text('[Desktop Entry]\nType=Application\nName[ru]=Тест\nExec=/usr/bin/printf "a,b" %U\nX-Unknown=keep\n')
            assert not job('apps.autostart',id='org.hics.AutoFixture',path=str(desktop),enabled=True)['error']
            saved=(base/'config/autostart/org.hics.AutoFixture.desktop').read_text();assert 'Exec=/usr/bin/printf "a,b" %U' in saved and 'Name[ru]=Тест' in saved,saved
            destination=base/'destination';destination.mkdir()
            copy=job('transfer.copy',sources=[str(docs/'public.txt')],target=str(destination));assert not copy['error'],copy
            assert (destination/'public.txt').read_text()==(docs/'public.txt').read_text()
            assert job('transfer.copy',sources=[str(docs/'public.txt')],target=str(destination))['error']
            transfer=job('transfer.send',address='00:11:22:33:44:55',path=str(docs/'public.txt'));assert not transfer['error'],transfer
            report=call('Report','fixture','transfer.copy','running','0.25',str(os.getpid()),'');assert report.get('id'),report
            assert any(row['id']==report['id'] and row['progress']==.25 for row in call('Status')['jobs'])
            assert call('Report','fixture','transfer.copy','completed','1.0',str(os.getpid()),'')['id']==report['id']
            acknowledged=subprocess.check_output(['gdbus','call','--session','--dest','org.hics.Desktop1','--object-path','/org/hics/Desktop1','--method','org.hics.Desktop1.Acknowledge',report['id']],text=True)
            assert 'true' in acknowledged
            result=job('diagnostics.check');encoded=json.dumps(result);assert 'ultrasecret' not in encoded and str(base) not in encoded,result
            rows=call('Status')['jobs'];assert rows and all(row['finished'] for row in rows)
            assert not any(row['operation'].startswith(('input.','comfort.','integration.')) for row in rows),rows
            external=call('Report','surviving-fixture','update.install','running','0.1',str(os.getpid()),'')['id']
            daemon.terminate();daemon.wait(timeout=5)
            state_path=base/'state/hics/desktop/jobs.json'; state=json.loads(state_path.read_text());assert 'arguments' not in json.dumps(state)
            assert state_path.stat().st_mode & 0o777 == 0o600
            assert state_path.parent.stat().st_mode & 0o777 == 0o700
            assert any(row.get('result',{}).get('checks') for row in state['jobs']),state
            daemon=subprocess.Popen([os.environ.get('HICS_TEST_DESKTOP_DAEMON',str(ROOT/'build/native/desktop/hics-desktopd'))],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            time.sleep(.2)
            assert call('Status')['comfort']['focus']['phase']=='work'
            assert call('Status')['comfort']['awakeDeadline']>time.time()*1000
            assert not job('comfort.focus-stop')['error']
            assert call('Status')['comfort']['awakeDeadline']>0
            restored=call('Status')['jobs'];assert len(restored)==len(rows)+1
            assert any(row['id']==external and not row['finished'] for row in restored),restored
            assert call('Report','surviving-fixture','update.install','completed','1.0',str(os.getpid()),'')['id']==external
            # Restart with an elapsed deadline: one full break, no busy loop or
            # automatic new work interval, including malformed persisted rounds.
            daemon.terminate();daemon.wait(timeout=5)
            comfort_path=base/'state/hics/desktop/comfort.json'
            value=json.loads(comfort_path.read_text());value['focus']={'phase':'work','deadline':int(time.time()*1000)-1000,'rounds':0,'longBreakSeconds':60};comfort_path.write_text(json.dumps(value))
            daemon=subprocess.Popen([os.environ.get('HICS_TEST_DESKTOP_DAEMON',str(ROOT/'build/native/desktop/hics-desktopd'))],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            time.sleep(.2)
            elapsed=call('Status')['comfort']['focus']
            assert elapsed['phase']=='break' and elapsed['deadline']>time.time()*1000,elapsed
            assert not job('comfort.focus-stop')['error']
            print('DESKTOP_SERVICE_OK')
        finally:
            mock.terminate();mock.wait(timeout=3)
            daemon.terminate()
            try:daemon.wait(timeout=5)
            except subprocess.TimeoutExpired:daemon.kill();daemon.wait()

if __name__=='__main__':
    import sys
    if '--fixture' in sys.argv:fixture()
    else:unittest.main()
