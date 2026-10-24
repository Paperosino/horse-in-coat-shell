#pragma once
#include <QHash>
#include <QMutex>
#include <QMutexLocker>
#include <QString>
#include <algorithm>
namespace System {
// Shared job accounting outlives the Broker. Per-connection quotas isolate
// clients; per-UID quotas stop reconnects from monopolizing the worker pool.
class Admission {
public:
  enum class Result { Allowed, Busy, RateLimited, Stopping };
  Result reserve(uint uid, const QString& sender, qint64 now) {
    QMutexLocker lock(&m_mutex);
    if (m_stopping) return Result::Stopping;
    if (!m_users.contains(uid)) {
      for (auto it = m_users.begin(); it != m_users.end(); ) {
        if (!it->pending && now - it->updated >= 60000) it = m_users.erase(it);
        else ++it;
      }
      if (m_users.size() >= 256) return Result::Busy;
      m_users.insert(uid, User{40.0, now, 0});
    }
    if (!m_callers.contains(sender)) {
      if (m_callers.size() >= 1024) {
        auto oldest = m_callers.end();
        for (auto it = m_callers.begin(); it != m_callers.end(); ++it)
          if (!it->pending && (oldest == m_callers.end() || it->updated < oldest->updated)) oldest = it;
        if (oldest == m_callers.end()) return Result::Busy;
        m_callers.erase(oldest);
      }
      m_callers.insert(sender, Caller{uid, 10.0, now, 0, false});
    }
    auto& caller = m_callers[sender];
    if (caller.uid != uid) return Result::Busy;
    caller.tokens = std::min(10.0, caller.tokens + std::max<qint64>(0, now - caller.updated) * .01);
    caller.updated = now;
    if (caller.tokens < 1.0) return Result::RateLimited;
    caller.tokens -= 1.0;
    auto& user = m_users[uid];
    user.tokens = std::min(40.0, user.tokens + std::max<qint64>(0, now - user.updated) * .04);
    user.updated = now;
    if (user.tokens < 1.0) return Result::RateLimited;
    if (m_pending >= 16 || user.pending >= 2 || caller.pending >= 1) return Result::Busy;
    user.tokens -= 1.0;
    ++caller.pending; ++user.pending; ++m_pending;
    return Result::Allowed;
  }
  void finish(uint uid, const QString& sender) {
    QMutexLocker lock(&m_mutex);
    auto caller = m_callers.find(sender); auto user = m_users.find(uid);
    if (caller != m_callers.end() && caller->uid == uid && caller->pending > 0 && user != m_users.end()) {
      --caller->pending; --user->pending; --m_pending;
      if (caller->disconnected) m_callers.erase(caller);
    }
  }
  void disconnected(const QString& sender) {
    QMutexLocker lock(&m_mutex);
    auto it = m_callers.find(sender);
    if (it == m_callers.end()) return;
    if (!it->pending) m_callers.erase(it);
    else it->disconnected = true;
  }
  void stop() { QMutexLocker lock(&m_mutex); m_stopping = true; }
  bool stopping() const { QMutexLocker lock(&m_mutex); return m_stopping; }
  int pending() const { QMutexLocker lock(&m_mutex); return m_pending; }
private:
  struct User { double tokens; qint64 updated; int pending; };
  struct Caller { uint uid; double tokens; qint64 updated; int pending; bool disconnected; };
  mutable QMutex m_mutex;
  QHash<uint, User> m_users;
  QHash<QString, Caller> m_callers;
  int m_pending = 0;
  bool m_stopping = false;
};
}
