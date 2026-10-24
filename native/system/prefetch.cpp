// Best-effort page-cache hints in a killable low-priority helper, never the UI.
#include <algorithm>
#include <cerrno>
#include <climits>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <poll.h>
#include <string>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/vfs.h>
#include <unistd.h>
int main(int argc, char **argv) {
  if (argc != 3)
    return 2;
  char *end = nullptr;
  const long mib = strtol(argv[2], &end, 10);
  if (!end || *end || mib < 1 || mib > 32 || std::strlen(argv[1]) > 4096)
    return 2;
  const auto parent = getppid();
  prctl(PR_SET_PDEATHSIG, SIGTERM);
  if (getppid() != parent)
    return 1;
  if (setpriority(PRIO_PROCESS, 0, 19) ||
      syscall(SYS_ioprio_set, 1, 0, 3 << 13))
    return 1;
  std::string executable = argv[1];
  char resolved[PATH_MAX];
  if (executable.find('/') == std::string::npos) {
    const char *raw = getenv("PATH");
    std::string paths = raw ? raw : "/usr/bin:/bin";
    size_t offset = 0;
    bool found = false;
    while (offset <= paths.size()) {
      auto end = paths.find(':', offset);
      if (end == std::string::npos)
        end = paths.size();
      auto dir = paths.substr(offset, end - offset);
      if (!dir.empty() && dir.front() == '/') {
        auto candidate = dir + '/' + executable;
        if (access(candidate.c_str(), X_OK) == 0) {
          executable = candidate;
          found = true;
          break;
        }
      }
      offset = end + 1;
    }
    if (!found)
      return 1;
  }
  if (!realpath(executable.c_str(), resolved) || access(resolved, X_OK))
    return 1;
  const int fd = open(resolved, O_RDONLY | O_CLOEXEC | O_NONBLOCK | O_NOFOLLOW);
  if (fd < 0)
    return 1;
  struct stat st{};
  struct statfs fs{};
  const bool local = !fstatfs(fd, &fs) &&
                     (fs.f_type == 0xEF53 || fs.f_type == 0x58465342 ||
                      fs.f_type == 0x9123683E || fs.f_type == 0x01021994 ||
                      fs.f_type == 0x794c7630 || fs.f_type == 0x2fc12fc1);
  long long advised = 0;
  if (local && !fstat(fd, &st) && S_ISREG(st.st_mode)) {
    const auto limit = std::min<long long>(mib * 1024 * 1024, st.st_size);
    for (long long offset = 0; offset < limit; offset += 256 * 1024) {
      pollfd input{STDIN_FILENO, POLLIN | POLLHUP, 0};
      if (poll(&input, 1, 2) > 0 && (input.revents & (POLLHUP | POLLERR)))
        break;
      const auto length = std::min<long long>(256 * 1024, limit - offset);
      if (posix_fadvise(fd, offset, length, POSIX_FADV_WILLNEED))
        break;
      advised += length;
    }
  }
  close(fd);
  printf("{\"advisedBytes\":%lld}\n", advised);
  return 0;
}
