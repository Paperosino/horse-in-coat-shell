#pragma once
#include <QDateTime>
#include <QString>
#include <cstring>
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
namespace hics::cleanup {
struct Result {
  quint64 bytes = 0;
  int files = 0, failed = 0;
  bool partial = false;
};
// Resolve every directory component without following symlinks. Deletions are
// relative to pinned directory FDs, so renaming a path cannot redirect unlink.
inline int directory(const QString &path) {
  if (!path.startsWith(u'/'))
    return -1;
  int fd = open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
  if (fd < 0)
    return -1;
  for (const auto &part : path.split(u'/', Qt::SkipEmptyParts)) {
    if (part == QStringLiteral(".") || part == QStringLiteral("..")) {
      close(fd);
      return -1;
    }
    const auto bytes = part.toLocal8Bit();
    int next = openat(fd, bytes.constData(),
                      O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    close(fd);
    if (next < 0)
      return -1;
    fd = next;
  }
  return fd;
}
inline void walk(int fd, Result &result, bool remove, qint64 before,
                 int depth = 0) {
  if (depth > 32 || result.files >= 100000) {
    result.partial = true;
    return;
  }
  auto *dir = fdopendir(dup(fd));
  if (!dir) {
    ++result.failed;
    return;
  }
  while (auto *entry = readdir(dir)) {
    if (std::strcmp(entry->d_name, ".") == 0 ||
        std::strcmp(entry->d_name, "..") == 0)
      continue;
    if (++result.files >= 100000) {
      result.partial = true;
      break;
    }
    struct stat info{};
    if (fstatat(fd, entry->d_name, &info, AT_SYMLINK_NOFOLLOW) != 0)
      continue;
    if (S_ISDIR(info.st_mode)) {
      int child = openat(fd, entry->d_name,
                         O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
      if (child >= 0) {
        walk(child, result, remove, before, depth + 1);
        close(child);
      }
      continue;
    }
    if (!S_ISREG(info.st_mode))
      continue;
    result.bytes += quint64(info.st_size > 0 ? info.st_size : 0);
    if (remove && (before == 0 || info.st_mtime < before) &&
        unlinkat(fd, entry->d_name, 0) != 0)
      ++result.failed;
  }
  closedir(dir);
}
inline Result scan(const QString &path, bool remove = false,
                   qint64 before = 0) {
  Result result;
  int fd = directory(path);
  if (fd < 0)
    return result;
  walk(fd, result, remove, before);
  close(fd);
  return result;
}
} // namespace hics::cleanup
