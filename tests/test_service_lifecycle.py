"""Service subscriptions must be safe across synchronous signal reentry."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
SERVICES=ROOT/'shell/plugin/src/Hyprstack/Services'
class ServiceLifecycleTests(unittest.TestCase):
    def test_reentrant_first_subscription_and_destroyed_subscribers(self):
        with tempfile.TemporaryDirectory(prefix='hics-service-lifecycle-') as directory:
            base=Path(directory)
            flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
            moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
            subprocess.run([str(moc),str(SERVICES/'service.hpp'),'-o',str(base/'moc.cpp')],check=True)
            (base/'probe.cpp').write_text('''#include "service.hpp"
#include <QCoreApplication>
using namespace hyprstack::services;
class Probe:public Service {
public:int starts=0,stops=0;QObject* secondary=nullptr;
void start()override{++starts;if(starts==1)ref(secondary);}
void stop()override{++stops;}
};
int main(int argc,char**argv){QCoreApplication app(argc,argv);Probe p;QObject a;auto*b=new QObject;p.secondary=b;
p.ref(&a);if(p.starts!=1)return 1;p.ref(&a);if(p.starts!=1)return 2;
p.unref(&a);if(p.stops!=0)return 3;delete b;if(p.stops!=1)return 4;
p.unref(&a);if(p.stops!=1)return 5;return 0;}''')
            binary=base/'probe'
            subprocess.run(['c++','-std=c++20','-fPIC',str(base/'probe.cpp'),str(base/'moc.cpp'),str(SERVICES/'service.cpp'),'-I',str(SERVICES),*flags,'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True,timeout=3)
