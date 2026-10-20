"""Exercise feature boundaries with real archives, temporary XDG homes and a
local streaming server. No compositor state or user's data is changed."""
import contextlib,importlib,io,json,os,stat,sys,tempfile,threading,unittest,zipfile
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shell/assets'))

class Features(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.root/'config'),'XDG_DATA_HOME':str(self.root/'data'),'XDG_STATE_HOME':str(self.root/'state')});self.env.start()
        import feature_common,plugin_manager,live_wallpapers,assistant_backend,system_controls
        self.common=importlib.reload(feature_common)
        self.plugins=importlib.reload(plugin_manager);self.walls=importlib.reload(live_wallpapers)
        self.ai=importlib.reload(assistant_backend);self.system=importlib.reload(system_controls)
    def tearDown(self):self.env.stop();self.temp.cleanup()
    def plugin(self,version='1'):
        path=self.root/('source-'+version);path.mkdir()
        (path/'manifest.json').write_text(json.dumps({'api':'hyprstack-1','id':'fixture','name':'Fixture','version':version,'entryPoints':{'main':'Main.qml'},'settingsSchema':[{'key':'count','type':'int','default':1,'min':0,'max':10}]}))
        (path/'Main.qml').write_text('import QtQuick\nItem { required property var pluginApi }')
        return path
    def test_plugin_install_enable_update_rollback_and_trash(self):
        p=self.plugins;p.install(str(self.plugin('1')));self.assertFalse(p.find('fixture')['enabled'])
        p.enable('fixture',True);self.assertTrue(p.find('fixture')['enabled'])
        p.install(str(self.plugin('2')),True);self.assertEqual(p.find('fixture')['version'],'2')
        backups=sorted((self.common.STATE/'plugin-backups/fixture').glob('*'));self.assertEqual(len(backups),1)
        p.remove('fixture');self.assertFalse((p.USER/'fixture').exists());self.assertTrue(any(p.TRASH.iterdir()))
        backups[-1].rename(p.USER/'fixture');self.assertEqual(p.find('fixture')['version'],'1')
    def test_manifest_cannot_escape_plugin(self):
        source=self.plugin();d=json.loads((source/'manifest.json').read_text());d['entryPoints']['main']='../outside.qml';(source/'manifest.json').write_text(json.dumps(d));(source.parent/'outside.qml').write_text('import QtQuick; Item {}')
        with self.assertRaises(ValueError):self.plugins.install(str(source))
    def test_zip_traversal_is_rejected(self):
        archive=self.root/'bad.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('../../escaped','bad')
        with self.assertRaises(ValueError):self.plugins.install(str(archive))
        self.assertFalse((self.root/'escaped').exists())
    def test_symlink_archive_is_rejected(self):
        archive=self.root/'bad-link.zip'
        with zipfile.ZipFile(archive,'w') as z:
            entry=zipfile.ZipInfo('link');entry.create_system=3;entry.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(entry,'/etc/passwd')
        with self.assertRaises(ValueError):self.plugins.install(str(archive))
    def test_luau_plugin_is_not_misrepresented_as_qml(self):
        source=self.root/'luau';source.mkdir();(source/'plugin.toml').write_text('id="tadomika_ari/w-engine"\nname="W Engine"\nplugin_api=9\n')
        m=self.plugins.manifest(source);self.assertFalse(m['compatible']);self.assertEqual(m['adapter'],'wallpaper-engine');self.assertIn('Luau',m['issues'][0])
    def test_qml_compatibility_reports_unavailable_services(self):
        source=self.root/'noctalia';source.mkdir();(source/'manifest.json').write_text(json.dumps({'id':'legacy','name':'Legacy','entryPoints':{'main':'Main.qml'}}));(source/'Main.qml').write_text('import QtQuick\nimport qs.Services\nItem { Component.onCompleted: AudioService.toggleMute() }')
        self.assertFalse(self.plugins.manifest(source)['compatible'])
    def test_settings_validation_preserves_preferences(self):
        p=self.plugins;p.install(str(self.plugin()));p.save_settings('fixture',{'count':3})
        with self.assertRaises(ValueError):p.save_settings('fixture',{'count':999})
        self.assertEqual(p.find('fixture')['settings']['count'],3)
    def test_workshop_null_properties_and_multiple_libraries(self):
        root=self.root/'431960';item=root/'42';item.mkdir(parents=True);(item/'project.json').write_text(json.dumps({'title':'Test','type':'video','general':None}));(item/'preview.jpg').write_bytes(b'preview')
        self.common.atomic_json(self.walls.CONFIG_FILE,{'workshopPaths':[str(root)]})
        library=self.walls.library();fixture=next(e for e in library['entries'] if e['id']=='42');self.assertEqual(fixture['properties'],{});self.assertTrue(fixture['preview'].endswith('preview.jpg'))
    def test_engine_arguments_keep_properties_separate(self):
        source=self.root/'wallpaper';source.mkdir();(source/'project.json').write_text('{}')
        cmd=self.walls.engine_command('DP-3',{'kind':'engine','source':str(source),'properties':{'text':'a; $(touch /tmp/not-a-command)','enabled':True},'muted':True})
        self.assertIn('text=a; $(touch /tmp/not-a-command)',cmd);self.assertIn('--silent',cmd);self.assertEqual(cmd[cmd.index('--bg')+1],str(source))
        with self.assertRaises(ValueError):self.walls.engine_command('DP-3',{'kind':'engine','source':str(source),'properties':{'--escape':'x'}})
    def test_compositor_rejection_does_not_write_settings(self):
        with patch.object(self.system,'run',side_effect=ValueError('not supported')):
            with self.assertRaises(ValueError):self.system.apply_change('input.sensitivity',0.2)
        self.assertFalse((self.common.CONFIG/'system-controls.json').exists())
    def test_lua_hyphenated_keys_and_persistent_hook(self):
        self.common.CONFIG.mkdir(parents=True);(self.common.CONFIG/'hypr-user.lua').write_text('for _,name in ipairs({"keyboard.lua", "local.lua"}) do end\n')
        with patch.object(self.system,'run',return_value='ok'):self.system.apply_change('input.touchpad.tap-to-click',False)
        self.assertIn('["tap-to-click"]=false',(self.common.CONFIG/'system.lua').read_text());self.assertIn('"system.lua", "local.lua"',(self.common.CONFIG/'hypr-user.lua').read_text())
    def test_autostart_override_retains_desktop_exec_codes(self):
        p=self.root/'config/autostart/test.desktop';p.parent.mkdir(parents=True);p.write_text('[Desktop Entry]\nType=Application\nName=Test\nExec=editor %U\n')
        self.system.autostart_set('test.desktop',False);self.assertIn('editor %U',p.read_text());self.assertFalse(next(x for x in self.system.autostart_list() if x['id']=='test.desktop')['enabled'])
    def test_streaming_chat_and_private_credentials(self):
        captured={}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured['path']=self.path;captured['auth']=self.headers.get('Authorization');captured['body']=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                self.send_response(200);self.send_header('Content-Type','application/x-ndjson');self.end_headers()
                for part in [{'message':{'content':'Привет '}},{'message':{'content':'мир'},'done':True}]:self.wfile.write((json.dumps(part)+'\n').encode());self.wfile.flush()
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            self.ai.save({'endpoint':f'http://127.0.0.1:{server.server_port}','model':'fixture','apiKey':'private-token'})
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream):self.ai.chat({'messages':[{'role':'user','content':'test'}]})
            events=[json.loads(s) for s in stream.getvalue().splitlines()];self.assertEqual(''.join(x.get('delta','') for x in events),'Привет мир');self.assertTrue(events[-1]['done'])
            self.assertEqual(captured['path'],'/api/chat');self.assertEqual(captured['auth'],'Bearer private-token');self.assertEqual(self.ai.history()['messages'][-1]['content'],'Привет мир')
            key=self.common.CONFIG/'assistant-key.json';self.assertEqual(stat.S_IMODE(key.stat().st_mode),0o600);self.assertNotIn('private-token',self.ai.CONF.read_text())
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()

class ThemeImport(unittest.TestCase):
    def test_noctalia_roles_are_preserved_and_missing_m3_roles_generated(self):
        import theme_manager
        source={'name':'Noctalia fixture','dark':{'mPrimary':'#ff00aa','mSurface':'#121212','mOnSurface':'#eeeeee','mSecondary':'#44aaff'}}
        adapted=theme_manager.adapt_external_theme(source)
        theme=theme_manager.custom_theme(adapted,'fixture')
        colors=theme['variants'][0]['colours']
        self.assertEqual(colors['primary'],'ff00aa');self.assertEqual(colors['surface'],'121212');self.assertEqual(colors['secondary'],'44aaff');self.assertIn('surfaceContainerHigh',colors)
