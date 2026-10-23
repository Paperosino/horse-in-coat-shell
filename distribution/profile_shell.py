#!/usr/bin/env python3
"""Sample the running hics shell without changing its configuration."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time


def shell_pid():
    runner = subprocess.check_output(['systemctl', '--user', 'show', 'hic-session.service',
                                     '--property=MainPID', '--value'], text=True).strip()
    pending = [int(runner)]
    while pending:
        pid = pending.pop()
        try:
            command = Path(f'/proc/{pid}/comm').read_text().strip()
            if command in ('hics-qs', 'quickshell'):
                return pid
            pending.extend(map(int, Path(f'/proc/{pid}/task/{pid}/children').read_text().split()))
        except FileNotFoundError:
            continue
    raise RuntimeError('No running hics shell in hic-session.service')


def sample(pid):
    # comm may contain spaces and parentheses. Fields start after its final ')'.
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return dict(ticks=int(fields[11]) + int(fields[12]),
                rssBytes=int(fields[21]) * os.sysconf('SC_PAGE_SIZE'), start=fields[19])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int)
    parser.add_argument('--seconds', type=float, default=10)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 60:
        parser.error('--seconds must be between 1 and 60')
    pid = args.pid or shell_pid()
    first = sample(pid)
    started = time.monotonic()
    samples = [first]
    while time.monotonic() - started < args.seconds:
        time.sleep(min(.25, max(0, args.seconds - (time.monotonic() - started))))
        current = sample(pid)
        if current['start'] != first['start']:
            raise RuntimeError('Shell restarted during measurement; repeat the sample')
        samples.append(current)
    elapsed = time.monotonic() - started
    print(json.dumps(dict(pid=pid, seconds=round(elapsed, 3),
        cpuPercentOneCore=round((samples[-1]['ticks'] - first['ticks']) /
                               os.sysconf('SC_CLK_TCK') / elapsed * 100, 2),
        rssMiB=round(samples[-1]['rssBytes'] / 2**20, 2),
        rssPeakMiB=round(max(s['rssBytes'] for s in samples) / 2**20, 2)), indent=2))


if __name__ == '__main__':
    main()
