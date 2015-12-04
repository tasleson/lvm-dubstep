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
import dbus
from job import Job

_rlock = threading.RLock()
_thread_list = list()


def _range_append(cmd, device, start, end):

    if (start, end) == (0, 0):
        cmd.append(device)
    else:
        if start != 0 and end == 0:
            cmd.append("%s-%d:-" % (device, start))
        else:
            cmd.append("%s-%d:%d" %
                       (device, start, end))


def pv_move_lv_cmd(move_options, lv_full_name,
                    pv_source, pv_source_range, pv_dest_range_list):
    cmd = ['pvmove', '-i', '1']
    cmd.extend(options_to_cli_args(move_options))

    if lv_full_name:
        cmd.extend(['-n', lv_full_name])

    _range_append(cmd, pv_source, *pv_source_range)

    if len(pv_dest_range_list):
        for i in pv_dest_range_list:
            _range_append(cmd, *i)

    return cmd


def move(interface_name, lv_name, pv_src_obj, pv_source_range,
            pv_dests_and_ranges, move_options):
    """
    Common code for the pvmove handling.  As moves are usually time consuming
    we will always be returning a job.
    :param interface_name:  What dbus interface we are providing for
    :param lv_name:     Optional (None or name of LV to move)
    :param pv_src_obj:  dbus object patch for source PV
    :param pv_source_range: (0,0 to ignore, else start, end segments)
    :param pv_dests_and_ranges: Array of PV object paths and start/end segs
    :param move_options: Hash with optional arguments
    :return: Object path to job object
    """
    pv_dests = []
    pv_src = cfg.om.get_by_path(pv_src_obj)
    if pv_src:

        # Check to see if we are handling a move to a specific
        # destination(s)
        if len(pv_dests_and_ranges):
            for pr in pv_dests_and_ranges:
                pv_dbus_obj = cfg.om.get_by_path(pr[0])
                if not pv_dbus_obj:
                    raise dbus.exceptions.DBusException(
                        interface_name,
                        'PV Destination (%s) not found' % pr[0])

                pv_dests.append((pv_dbus_obj.lvm_id, pr[1], pr[2]))

        # Generate the command line for this command, but don't
        # execute it.
        cmd = pv_move_lv_cmd(move_options,
                                lv_name,
                                pv_src.lvm_id,
                                pv_source_range,
                                pv_dests)

        # Create job object to be used while running the command
        job_obj = Job(None)
        cfg.om.register_object(job_obj)
        add(cmd, job_obj)
        return job_obj.dbus_object_path()
    else:
        raise dbus.exceptions.DBusException(
            interface_name, 'pv_src_obj (%s) not found' % pv_src_obj)


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