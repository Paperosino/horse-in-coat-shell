"""Compile real native policy/controller; isolated settings, no host tuning."""
import os,shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SERVICES=ROOT/'shell/plugin/src/Hyprstack/Services'
class PerformanceNative(unittest.TestCase):
 def test_hysteresis_missing_samples_and_recovery(self):
  source='''#include "performancepolicy.hpp"
#include <cassert>
#include <limits>
int main(){hics::performance::QualityPolicy p;
auto s=[&](double gpu,double temp,long t,bool adaptive=true,bool thermal=true){p.sample(gpu,temp,adaptive,thermal,0,85,50,85,75,t,5000);};
s(-1,-1,10000);assert(p.level==2 && !p.hot);
s(90,70,10000);s(90,70,12000);s(90,70,14000);assert(p.level==1);
s(90,70,16000);s(90,70,18000);assert(p.level==1);s(90,70,20000);assert(p.level==0);
s(-1,70,22000);assert(p.level==0);
for(long t=24000;t<=32000;t+=2000)s(20,70,t);assert(p.level==1);
s(90,90,34000);assert(p.hot);s(20,74,36000);s(20,74,38000);assert(p.hot);s(20,74,40000);assert(!p.hot);
s(std::numeric_limits<double>::quiet_NaN(),-1,42000);assert(p.level==1);
s(100,100,44000,false,false);assert(p.level==2 && !p.hot);
}'''
  self.compile_run(source,[],[],includes=[SERVICES])
 def compile_run(self,source,sources,libraries,includes=()):
  with tempfile.TemporaryDirectory(prefix='hics-performance-native-') as directory:
   base=Path(directory);(base/'main.cpp').write_text(source)
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',*libraries],text=True)) if libraries else []
   subprocess.run(['c++','-std=c++20','-O2','-fPIC',str(base/'main.cpp'),*map(str,sources),*['-I'+str(p) for p in includes],*flags,'-o',str(base/'probe')],check=True)
   env=dict(os.environ,XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'))
   subprocess.run([str(base/'probe')],env=env,check=True,timeout=15)
 def test_controller_validates_persists_and_classifies_real_fullscreen(self):
  with tempfile.TemporaryDirectory(prefix='hics-performance-moc-') as directory:
   moc=Path(directory)/'moc.cpp';mocbin=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','Qt6Qml'],text=True))
   subprocess.run([str(mocbin),str(SERVICES/'runtimeperformance.hpp'),*flags,'-o',str(moc)],check=True)
   source='''#include "runtimeperformance.hpp"
#include <QCoreApplication>
#include <QFile>
#include <QStandardPaths>
#include <cassert>
int main(int argc,char**argv){QCoreApplication app(argc,argv);
using hyprstack::services::RuntimePerformance;
{RuntimePerformance p;
assert(!p.status().value("monitoring").toBool());assert(p.quality()==2);
assert(!p.set("unknown",true));assert(!p.set("sampleInterval",1));assert(!p.set("prefetchMiB",999999));
assert(!p.set("gpuLow",95));assert(!p.set("temperatureLow",85));assert(!p.set("autoGameMode",QString("true")));
assert(p.set("autoGameMode",true));
QVariantMap w{{"class","steam_app_123"},{"mapped",true},{"pid",int(QCoreApplication::applicationPid())},{"fullscreen",1},{"xwayland",false}};
p.observeWindow(w);assert(!p.autoGame());assert(p.gamePid()==QCoreApplication::applicationPid());
w["fullscreen"]=2;p.observeWindow(w);assert(p.autoGame());
p.setSessionState(false,false,true);assert(!p.autoGame());p.setSessionState(false,false,false);assert(p.autoGame());
w["class"]="org.gnome.Nautilus";p.observeWindow(w);assert(!p.autoGame());
w["class"]="steam";p.observeWindow(w);assert(!p.autoGame());
assert(p.set("gameRules",QStringList{"org.example.Game*"}));w["class"]="org.example.GameOne";p.observeWindow(w);assert(p.autoGame());
w["mapped"]=false;p.observeWindow(w);assert(!p.autoGame());
assert(p.set("feralGameMode",true));assert(p.set("performanceProfile",true));assert(!p.settings().value("feralGameMode").toBool());assert(p.set("performanceProfile",false));
assert(p.set("gpuLow",10));assert(p.set("gpuHigh",40));
assert(p.set("adaptiveQuality",true));assert(p.status().value("monitoring").toBool());
assert(p.set("adaptiveQuality",false));assert(!p.status().value("monitoring").toBool());
assert(p.set("prefetch",true));p.observeWindow({{"class","org.example.One"}},"one","true");p.forgetHistory();
assert(p.set("prefetch",false));assert(!p.status().value("monitoring").toBool());}
{RuntimePerformance p;assert(p.settings().value("gpuLow").toInt()==10 && p.settings().value("gpuHigh").toInt()==40);assert(p.settings().value("autoGameMode").toBool());assert(p.settings().value("gameRules").toStringList()==QStringList{"org.example.Game*"});assert(!p.status().value("monitoring").toBool());}
QFile config(QStandardPaths::writableLocation(QStandardPaths::ConfigLocation)+"/hics/performance.json");assert(config.permissions()==(QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ReadUser|QFileDevice::WriteUser));
}'''
   self.compile_run(source,[SERVICES/'runtimeperformance.cpp',moc],['Qt6Core','Qt6Qml'],[SERVICES])
 def test_prediction_requires_history_allowlist_and_live_budget(self):
  source='''#include "prefetchpolicy.hpp"
#include <cassert>
#include <limits>
int main(){using namespace hics::performance;QList<Visit> v;
for(int i=0;i<3;++i){v.append({"a","/usr/bin/a",i*10});v.append({"b","/usr/bin/b",i*10+1});}v.append({"a","/usr/bin/a",30});
assert(!predict(v,"a",{},3,70,30,300));
auto p=predict(v,"a",{"b"},3,70,30,300);assert(p && p->id=="b" && p->confidence==100);
assert(!predict(v,"a",{"b"},4,70,30,300));assert(!predict(v,"a",{"b"},3,70,400,300));
assert(!predict(v,"a",{"b"},3,70,20,300));
v.append({"c","/usr/bin/c",31});v.append({"a","/usr/bin/a",32});
assert(!predict(v,"a",{"b"},3,90,32,300));
assert(prefetchBudget(20,30,0,0,50,75));assert(!prefetchBudget(60,30,0,0,50,75));
assert(!prefetchBudget(20,80,0,0,50,75));assert(!prefetchBudget(20,30,.2,0,50,75));
assert(!prefetchBudget(20,30,0,2,50,75));assert(!prefetchBudget(-1,30,0,0,50,75));
assert(!prefetchBudget(std::numeric_limits<double>::quiet_NaN(),30,0,0,50,75));
}'''
  self.compile_run(source,[],['Qt6Core'],[SERVICES])
 def test_dispatch_value_cache_survives_vector_mutations(self):
  with tempfile.TemporaryDirectory(prefix='hics-dispatch-cache-') as directory:
   base=Path(directory);api=base/'hyprland/src/plugins/PluginAPI.hpp';api.parent.mkdir(parents=True)
   api.write_text('''#pragma once
#include <string>
#include <vector>
#include <memory>
using HANDLE=void*;template<class T>using WP=std::weak_ptr<T>;
struct CRegion{};struct CTexPassElement{};
struct CFunctionHook{void* m_original;bool hook(){return true;}};
namespace HyprlandAPI {struct Symbol{std::string demangled;void* address;};
inline std::vector<Symbol> findFunctionsByName(HANDLE,const char*){return {{"Render::IElementRenderer::drawTex(test)",nullptr}};}
inline CFunctionHook* createFunctionHook(HANDLE,void*,void*){return new CFunctionHook{nullptr};}
inline void removeFunctionHook(HANDLE,CFunctionHook*h){delete h;}}
''')
   tex=base/'hyprland/src/render/pass/TexPassElement.hpp';tex.parent.mkdir(parents=True);tex.write_text('#pragma once\n#include <hyprland/src/plugins/PluginAPI.hpp>\n')
   source='''#include "dispatch.cpp"
#include <cassert>
int selected=0;
void first(void*,WP<CTexPassElement>,const CRegion&,hics::render::Draw){selected=1;}
void second(void*,WP<CTexPassElement>,const CRegion&,hics::render::Draw){selected=2;}
void third(void*,WP<CTexPassElement>,const CRegion&,hics::render::Draw){selected=3;}
int main(){using namespace hics::render;auto a=reinterpret_cast<void*>(1),b=reinterpret_cast<void*>(2);
assert(attach(a,first,10,true));assert(attach(b,second,20,false));dispatch(nullptr,{},{});assert(selected==1);
enable(second,true);dispatch(nullptr,{},{});assert(selected==2);
assert(attach(a,third,30,true));dispatch(nullptr,{},{});assert(selected==3);
enable(third,false);dispatch(nullptr,{},{});assert(selected==2);
detach(a);dispatch(nullptr,{},{});assert(selected==2);assert(diagnostics().activePriority==20);
detach(b);assert(diagnostics().participants==0);
}'''
   self.compile_run(source,[],[],[base,ROOT/'native/render-dispatch'])
