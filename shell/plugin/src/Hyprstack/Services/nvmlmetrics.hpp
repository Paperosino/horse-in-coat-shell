#pragma once
#include <QLibrary>
#include <algorithm>
namespace hics::performance {
// NVML's stable C ABI is optional. No polling subprocesses and no CUDA context.
class NvidiaMetrics {
public:
  ~NvidiaMetrics() { reset(); }
  void reset() {
    if (m_ready)
      m_shutdown();
    m_ready = false;
    m_attempted = false;
    m_library.unload();
  }
  bool sample(double &usage, double &temperature) {
    if (!m_attempted) {
      m_attempted = true;
      m_library.setFileName(QStringLiteral("libnvidia-ml.so.1"));
      auto init = reinterpret_cast<int (*)()>(m_library.resolve("nvmlInit_v2"));
      m_shutdown =
          reinterpret_cast<int (*)()>(m_library.resolve("nvmlShutdown"));
      m_count = reinterpret_cast<int (*)(unsigned *)>(
          m_library.resolve("nvmlDeviceGetCount_v2"));
      m_device = reinterpret_cast<int (*)(unsigned, void **)>(
          m_library.resolve("nvmlDeviceGetHandleByIndex_v2"));
      m_usage = reinterpret_cast<int (*)(void *, Utilization *)>(
          m_library.resolve("nvmlDeviceGetUtilizationRates"));
      m_temperature = reinterpret_cast<int (*)(void *, unsigned, unsigned *)>(
          m_library.resolve("nvmlDeviceGetTemperature"));
      if (init && m_shutdown && m_count && m_device && m_usage && m_temperature)
        m_ready = init() == 0;
    }
    if (!m_ready)
      return false;
    unsigned count = 0;
    if (m_count(&count))
      return false;
    bool valid = false;
    for (unsigned i = 0; i < std::min(count, 16u); ++i) {
      void *device = nullptr;
      if (m_device(i, &device))
        continue;
      Utilization utilization{};
      unsigned temp = 0;
      if (!m_usage(device, &utilization) && utilization.gpu <= 100) {
        usage = std::max(usage, double(utilization.gpu));
        valid = true;
      }
      if (!m_temperature(device, 0, &temp) && temp > 0 && temp < 150)
        temperature = std::max(temperature, double(temp));
    }
    return valid;
  }

private:
  struct Utilization {
    unsigned gpu, memory;
  };
  QLibrary m_library;
  bool m_ready = false, m_attempted = false;
  int (*m_shutdown)() = nullptr;
  int (*m_count)(unsigned *) = nullptr;
  int (*m_device)(unsigned, void **) = nullptr;
  int (*m_usage)(void *, Utilization *) = nullptr;
  int (*m_temperature)(void *, unsigned, unsigned *) = nullptr;
};
} // namespace hics::performance
