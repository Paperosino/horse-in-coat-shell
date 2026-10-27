"""Real CPU sensor transitions, with deterministic sensor and timer fixtures."""
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / 'shell/plugin/src/Hyprstack/Services'


class CpuSensorTests(unittest.TestCase):
    def test_missing_zero_valid_invalid_and_disappearing_sensor(self):
        with tempfile.TemporaryDirectory(prefix='hics-cpu-sensor-') as directory:
            base = Path(directory)
            source = base / 'probe.cpp'
            source.write_text(r'''
#include "cpu.hpp"
#include "sensorslib.hpp"
#include <QCoreApplication>
#include <QEvent>
#include <limits>
#include <cassert>
using namespace hyprstack::services;
namespace hyprstack::services {
// Isolate Cpu's real sampler from the dashboard configuration and tick policy.
TickingService::TickingService(QObject *parent):Service(parent) {}
int TickingService::updateInterval() const {return 1000;}
bool TickingService::eventFilter(QObject *, QEvent *) {return false;}
void TickingService::start() {}
void TickingService::stop() {}
namespace sensorslib {
std::optional<double> sample;
std::optional<double> cpuPackageTemp() {return sample;}
}
}
struct Probe:Cpu {void sample() {tick();}};
int main(int argc,char **argv) {
 QCoreApplication app(argc,argv);Probe cpu;int changed=0;
 QObject::connect(&cpu,&Cpu::temperatureChanged,[&]{++changed;});
 cpu.sample();assert(!cpu.temperatureAvailable()&&changed==0);
 sensorslib::sample=0.;cpu.sample();assert(cpu.temperatureAvailable()&&cpu.temperature()==0.&&changed==1);
 sensorslib::sample=43.;cpu.sample();assert(cpu.temperatureAvailable()&&cpu.temperature()==43.&&changed==2);
 sensorslib::sample=43.02;cpu.sample();assert(changed==2);
 sensorslib::sample=std::nullopt;cpu.sample();assert(!cpu.temperatureAvailable()&&changed==3);
 sensorslib::sample=std::numeric_limits<double>::quiet_NaN();cpu.sample();assert(!cpu.temperatureAvailable()&&changed==3);
 sensorslib::sample=std::numeric_limits<double>::infinity();cpu.sample();assert(!cpu.temperatureAvailable()&&changed==3);
 sensorslib::sample=39.;cpu.sample();assert(cpu.temperatureAvailable()&&cpu.temperature()==39.&&changed==4);
}
''')
            moc_root = Path(subprocess.check_output(
                ['qmake6', '-query', 'QT_HOST_LIBEXECS'], text=True).strip())
            generated = []
            for name in ('cpu', 'tickingservice', 'service'):
                output = base / ('moc_' + name + '.cpp')
                subprocess.run([str(moc_root / 'moc'), str(SERVICES / (name + '.hpp')),
                                '-o', str(output)], check=True, capture_output=True, timeout=15)
                generated.append(str(output))
            flags = shlex.split(subprocess.check_output(
                ['pkg-config', '--cflags', '--libs', 'Qt6Core', 'Qt6Qml'], text=True))
            result = subprocess.run(['c++', '-fPIC', '-std=c++20', '-I' + str(SERVICES),
                                     str(source), str(SERVICES / 'cpu.cpp'),
                                     str(SERVICES / 'service.cpp'), *generated, *flags,
                                     '-o', str(base / 'probe')],
                                    capture_output=True, text=True, timeout=40)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(base / 'probe')], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
