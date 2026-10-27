"""Production keyboard model lifetime/reentry; toast/config dependencies stubbed."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'shell/plugin/src/Hyprstack/Services'
PROBE = r'''
#include "hyprdevices.hpp"
#include <QCoreApplication>
#include <QJsonArray>
#include <QPointer>
#include <cassert>
using namespace hyprstack::services::hypr;
QJsonObject keyboard(const char *name){return {{"address","fixture"},{"name",name},{"layout","us"},{"main",true}};}
QJsonObject devices(const char *name){return {{"keyboards",QJsonArray{keyboard(name)}}};}
int main(int argc,char **argv){QCoreApplication app(argc,argv);const QByteArray mode(argv[1]);
 if(mode.startsWith("direct")){
  auto *kb=new HyprKeyboard(keyboard("old"));QPointer<HyprKeyboard> guard(kb);bool once=false;int changed=0;
  QObject::connect(kb,&HyprKeyboard::lastIpcObjectChanged,[&]{if(!once){once=true;if(mode=="direct-delete")delete kb;else kb->updateLastIpcObject(keyboard("superseded"));}});
  QObject::connect(kb,&HyprKeyboard::nameChanged,[&]{++changed;});
  kb->updateLastIpcObject(keyboard("intermediate"));
  if(mode=="direct-delete"){assert(!guard);return 0;}
  kb->updateLastIpcObject(keyboard("latest"));
  if(mode=="direct-pending-delete"){delete kb;QCoreApplication::processEvents();return 0;}
  QCoreApplication::processEvents();assert(kb->name()=="latest");assert(changed==2);delete kb;
 }else if(mode=="delete"){
  auto *owner=new HyprDevices;owner->updateLastIpcObject(devices("old"));auto list=owner->keyboards();auto *kb=list.at(&list,0);
  QPointer<HyprDevices> guard(owner);
  QObject::connect(kb,&HyprKeyboard::lastIpcObjectChanged,[owner]{delete owner;});
  owner->updateLastIpcObject({{"keyboards",QJsonArray{keyboard("new"),QJsonObject{{"address","second"},{"name","second"}}}}});assert(!guard);
 }else if(mode=="coalesce"){
  auto *owner=new HyprDevices;owner->updateLastIpcObject(devices("old"));auto list=owner->keyboards();auto *kb=list.at(&list,0);
  bool once=false;int changed=0;
  QObject::connect(kb,&HyprKeyboard::lastIpcObjectChanged,[&]{if(!once){once=true;owner->updateLastIpcObject(devices("superseded"));}});
  QObject::connect(kb,&HyprKeyboard::nameChanged,[&]{++changed;});
  owner->updateLastIpcObject(devices("intermediate"));owner->updateLastIpcObject(devices("latest"));
  QCoreApplication::processEvents();assert(kb->name()=="latest");assert(changed==2);delete owner;
 }else if(mode=="pending-delete"){
  auto *owner=new HyprDevices;owner->updateLastIpcObject(devices("old"));auto list=owner->keyboards();auto *kb=list.at(&list,0);
  QObject::connect(kb,&HyprKeyboard::lastIpcObjectChanged,[&]{owner->updateLastIpcObject(devices("pending"));});
  owner->updateLastIpcObject(devices("intermediate"));delete owner;QCoreApplication::processEvents();
 }else{
  HyprDevices owner;owner.updateLastIpcObject(devices("old"));auto list=owner.keyboards();auto *kb=list.at(&list,0);
  bool once=false;int changed=0;
  QObject::connect(kb,&HyprKeyboard::lastIpcObjectChanged,[&]{if(!once){once=true;owner.updateLastIpcObject(devices("latest"));}});
  QObject::connect(kb,&HyprKeyboard::nameChanged,[&]{++changed;assert(kb->name()=="intermediate"||kb->name()=="latest");});
  owner.updateLastIpcObject(devices("intermediate"));QCoreApplication::processEvents();assert(kb->name()=="latest");assert(changed==2);
 }
}
'''

class HyprDevicesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='hics-devices-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        for name in ('hyprdevices.cpp', 'hyprdevices.hpp'):
            source = Path(os.environ.get('HICS_TEST_DEVICES_SOURCE', SOURCE / name)) if name.endswith('.cpp') else SOURCE / name
            (cls.base/name).write_bytes(source.read_bytes())
        stubs = {
            'config/rootnodes.hpp': '''#pragma once
namespace hyprstack::config {struct UtilitiesToasts {bool capsLockChanged()const{return false;}bool numLockChanged()const{return false;}bool kbLayoutChanged()const{return false;}};struct Utilities {UtilitiesToasts*toasts(){static UtilitiesToasts t;return &t;}};struct ConfigSingleton {static ConfigSingleton*instance(){static ConfigSingleton c;return &c;}Utilities*utilities(){static Utilities u;return &u;}};}
''',
            'core/toaster.hpp': '''#pragma once
#include <QString>
namespace hyprstack::services {struct Toaster {static Toaster*instance(){static Toaster t;return &t;}void toast(const QString&,const QString&,const QString&) {}};}
''',
            'util/i18n.hpp': '''#pragma once
#include <QString>
#include <QVariantList>
namespace hyprstack::util::i18n {inline QString mark(const QString&s,const QVariantList& = {}){return s;}}
''',
        }
        for name, text in stubs.items():
            path = cls.base/name;path.parent.mkdir(exist_ok=True);path.write_text(text)
        (cls.base/'probe.cpp').write_text(PROBE)
        flags = shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Qml'],text=True))
        moc = Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
        subprocess.run([str(moc),str(cls.base/'hyprdevices.hpp'),*[f for f in flags if f.startswith(('-I','-D'))],'-o',str(cls.base/'moc.cpp')],check=True,capture_output=True)
        sanitizer = ['-fsanitize=address','-fno-omit-frame-pointer'] if os.environ.get('HICS_TEST_ASAN') else []
        result = subprocess.run(['c++','-std=c++23','-fPIC','-g',*sanitizer,'-I'+str(cls.base),str(cls.base/'probe.cpp'),str(cls.base/'hyprdevices.cpp'),str(cls.base/'moc.cpp'),*flags,'-o',str(cls.base/'probe')],capture_output=True,text=True,timeout=45)
        if result.returncode:raise RuntimeError(result.stderr)

    def test_signal_can_delete_owner(self):
        result = subprocess.run([str(self.base/'probe'),'delete'],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_nested_update_preserves_coherent_property_changes(self):
        result = subprocess.run([str(self.base/'probe'),'reenter'],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_newer_snapshot_supersedes_pending_reentrant_update(self):
        result = subprocess.run([str(self.base/'probe'),'coalesce'],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_destroy_with_pending_update(self):
        result = subprocess.run([str(self.base/'probe'),'pending-delete'],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_direct_keyboard_lifetime_and_reentry(self):
        for mode in ('direct-delete','direct-coalesce','direct-pending-delete'):
            with self.subTest(mode=mode):
                result = subprocess.run([str(self.base/'probe'),mode],capture_output=True,text=True,timeout=5)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
