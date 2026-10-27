"""Verify the actual allocator options at process startup, including user overrides."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AllocatorPolicyTests(unittest.TestCase):
    def test_diagnostic_build_can_disable_the_allocator_and_its_policy(self):
        with tempfile.TemporaryDirectory(prefix='hics allocator disabled ') as tmp:
            root = Path(tmp)
            (root / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.27)
project(quickshell LANGUAGES CXX)
option(USE_JEMALLOC "allocator" OFF)
add_executable(quickshell main.cpp)
''')
            (root / 'main.cpp').write_text('int main() { return 0; }\n')
            subprocess.run(['cmake', '-S', str(root), '-B', str(root / 'build'),
                            '-DCMAKE_PROJECT_quickshell_INCLUDE=' + str(ROOT / 'distribution/quickshell_allocator/configure.cmake')],
                           check=True, capture_output=True, timeout=20)
            subprocess.run(['cmake', '--build', str(root / 'build')], check=True,
                           capture_output=True, timeout=20)
            symbols = subprocess.check_output(['readelf', '-Ws', str(root / 'build/quickshell')], text=True, timeout=5)
            self.assertNotIn('malloc_conf', symbols)
            dynamic = subprocess.check_output(['readelf', '-d', str(root / 'build/quickshell')], text=True, timeout=5)
            self.assertNotIn('libjemalloc', dynamic)
            result = subprocess.run(['python3', str(ROOT / 'distribution/quickshell_allocator/verify.py'),
                                     str(root / 'build/quickshell')], capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('policy symbol is missing', result.stderr)

    def test_cmake_hook_sets_process_local_defaults_and_respects_user_override(self):
        with tempfile.TemporaryDirectory(prefix='hics allocator policy ') as tmp:
            root = Path(tmp)
            (root / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.27)
project(quickshell LANGUAGES CXX)
option(USE_JEMALLOC "allocator" ON)
add_executable(quickshell main.cpp)
if(USE_JEMALLOC)
 target_link_libraries(quickshell PRIVATE jemalloc)
endif()
''')
            (root / 'main.cpp').write_text('''#include <cstdio>
#include <cstdlib>
#include <sys/types.h>
#include <jemalloc/jemalloc.h>
int main() {
 ssize_t dirty = -2, muzzy = -2;
 bool background = true;
 size_t n = sizeof(dirty);
 if (mallctl("opt.dirty_decay_ms", &dirty, &n, nullptr, 0)) return 2;
 n = sizeof(muzzy);
 if (mallctl("opt.muzzy_decay_ms", &muzzy, &n, nullptr, 0)) return 3;
 n = sizeof(background);
 if (mallctl("opt.background_thread", &background, &n, nullptr, 0)) return 4;
 std::printf("%lld %lld %d %d\\n", (long long)dirty, (long long)muzzy,
             background, std::getenv("MALLOC_CONF") != nullptr);
}
''')
            env = dict(os.environ)
            env.pop('MALLOC_CONF', None)
            env.pop('LD_PRELOAD', None)
            subprocess.run(['cmake', '-S', str(root), '-B', str(root / 'build'),
                            '-DCMAKE_PROJECT_quickshell_INCLUDE=' + str(ROOT / 'distribution/quickshell_allocator/configure.cmake')],
                           check=True, capture_output=True, timeout=20, env=env)
            subprocess.run(['cmake', '--build', str(root / 'build')], check=True,
                           capture_output=True, timeout=20, env=env)
            command = [str(root / 'build/quickshell')]
            subprocess.run(['python3', str(ROOT / 'distribution/quickshell_allocator/verify.py'),
                            command[0]], check=True, capture_output=True, timeout=5)
            result = subprocess.check_output(command, text=True, env=env, timeout=5)
            self.assertEqual(result.strip(), '1000 0 0 0')
            env['MALLOC_CONF'] = 'dirty_decay_ms:1234'
            result = subprocess.check_output(command, text=True, env=env, timeout=5)
            self.assertEqual(result.strip(), '1234 0 0 1')


if __name__ == '__main__':
    unittest.main()
