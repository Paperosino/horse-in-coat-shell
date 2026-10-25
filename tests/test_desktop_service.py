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
        home=base/'home'; home.mkdir()
        docs=home/'Documents'; docs.mkdir()
        (docs/'public.txt').write_text('public searchable orchard')
        private=docs/'private'; private.mkdir(); (private/'secret.txt').write_text('ultrasecret sentinel')
        hidden=docs/'.hidden'; hidden.mkdir(); (hidden/'hidden.txt').write_text('hidden sentinel')
        outside=base/'outside'; outside.mkdir(); (outside/'outside.txt').write_text('outside sentinel')
        (docs/'link').symlink_to(outside, target_is_directory=True)
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
            assert not any(row['operation'].startswith('input.') for row in rows),rows
            external=call('Report','surviving-fixture','update.install','running','0.1',str(os.getpid()),'')['id']
            daemon.terminate();daemon.wait(timeout=5)
            state_path=base/'state/hics/desktop/jobs.json'; state=json.loads(state_path.read_text());assert 'arguments' not in json.dumps(state)
            assert state_path.stat().st_mode & 0o777 == 0o600
            assert state_path.parent.stat().st_mode & 0o777 == 0o700
            assert any(row.get('result',{}).get('checks') for row in state['jobs']),state
            daemon=subprocess.Popen([os.environ.get('HICS_TEST_DESKTOP_DAEMON',str(ROOT/'build/native/desktop/hics-desktopd'))],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            time.sleep(.2)
            restored=call('Status')['jobs'];assert len(restored)==len(rows)+1
            assert any(row['id']==external and not row['finished'] for row in restored),restored
            assert call('Report','surviving-fixture','update.install','completed','1.0',str(os.getpid()),'')['id']==external
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
