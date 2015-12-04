# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2015, Tony Asleson <tasleson@redhat.com>

import threading
import string
import subprocess
import cfg
import time
from cmdhandler import options_to_cli_args

_rlock = threading.RLock()
_thread_list = list()


def pv_move_lv_cmd(move_options, lv_full_name,
                    pv_source, pv_source_range, pv_dest, pv_dest_range):
    cmd = ['pvmove', '-i', '1']
    cmd.extend(options_to_cli_args(move_options))

    cmd.extend(['-n', lv_full_name])

    if pv_source_range[1] != 0:
        cmd.append("%s-%d:%d" %
                   (pv_source, pv_source_range[0], pv_source_range[1]))
    else:
        cmd.append(pv_source)

    if pv_dest:
        if pv_dest_range[1] != 0:
            cmd.append("%s-%d:%d" %
                       (pv_dest, pv_dest_range[0], pv_dest_range[1]))
        else:
            cmd.append(pv_dest)

    return cmd


def pv_move_reaper():
    while cfg.run.value != 0:
        with _rlock:
            num_threads = len(_thread_list) - 1
            if num_threads >= 0:
                for i in range(num_threads, -1, -1):
                    _thread_list[i].join(0)
                    if not _thread_list[i].is_alive():
                        _thread_list.pop(i)

        time.sleep(3)


def move_execute(command, move_job):
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, close_fds=True)
    lines_iterator = iter(process.stdout.readline, b"")
    for line in lines_iterator:
        if len(line) > 10:
            (device, ignore, percentage) = line.split(':')
            move_job.Percent = round(float(string.strip(percentage)[:-1]), 1)

    out = process.communicate()

    #print "DEBUG: EC %d, STDOUT %s, STDERR %s" % \
    #      (process.returncode, out[0], out[1])

    move_job.set_result(process.returncode, out[1])


def add(command, reporting_job):
    # Create the thread, get it running and then add it to the list
    t = threading.Thread(target=move_execute,
                            name="thread: " + ' '.join(command),
                            args=(command, reporting_job))
    t.start()

    with _rlock:
        _thread_list.append(t)
