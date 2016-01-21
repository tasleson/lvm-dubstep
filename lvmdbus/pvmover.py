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
import subprocess
from . import cfg
import time
from .cmdhandler import options_to_cli_args
import dbus
from .job import Job, JobState
from .utils import pv_range_append, pv_dest_ranges
from .request import RequestEntry

_rlock = threading.RLock()
_thread_list = list()


def pv_move_lv_cmd(move_options, lv_full_name,
                    pv_source, pv_source_range, pv_dest_range_list):
    cmd = ['pvmove', '-i', '1']
    cmd.extend(options_to_cli_args(move_options))

    if lv_full_name:
        cmd.extend(['-n', lv_full_name])

    pv_range_append(cmd, pv_source, *pv_source_range)
    pv_dest_ranges(cmd, pv_dest_range_list)

    return cmd


def _create_move_dbus_job(job_state):
    job_obj = Job(None, job_state)
    cfg.om.register_object(job_obj)
    return job_obj.dbus_object_path()


def move(interface_name, lv_name, pv_src_obj, pv_source_range,
         pv_dests_and_ranges, move_options, time_out):
    """
    Common code for the pvmove handling.
    :param interface_name:  What dbus interface we are providing for
    :param lv_name:     Optional (None or name of LV to move)
    :param pv_src_obj:  dbus object patch for source PV
    :param pv_source_range: (0,0 to ignore, else start, end segments)
    :param pv_dests_and_ranges: Array of PV object paths and start/end segs
    :param move_options: Hash with optional arguments
    :param time_out:
    :return: Object path to job object
    """
    rc = '/'
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
        job_state = JobState(None)
        add(cmd, job_state)

        if time_out == -1:
            # Waiting forever
            done = job_state.Wait(time_out)
            if not done:
                ec, err_msg = job_state.GetError
                raise dbus.exceptions.DBusException(
                    interface_name,
                    'Exit code %s, stderr = %s' % (str(ec), err_msg))
        elif time_out == 0:
            # Immediately create and return a job
            rc = _create_move_dbus_job(job_state)
        else:
            # Willing to wait for a bit
            done = job_state.Wait(time_out)
            if not done:
                rc = _create_move_dbus_job(job_state)

        return rc
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


def process_move_result(job_object, exit_code, error_msg):
    cfg.load(refresh=True, emit_signal=True)
    job_object.set_result(exit_code, error_msg)
    return None


# noinspection PyUnusedLocal
def empty_cb(disregard):
    pass


def move_execute(command, move_job):
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, close_fds=True)
    lines_iterator = iter(process.stdout.readline, b"")
    for line in lines_iterator:
        if len(line) > 10:
            (device, ignore, percentage) = line.decode("utf-8").split(':')
            move_job.Percent = round(float(percentage.strip()[:-1]), 1)

    out = process.communicate()

    #print "DEBUG: EC %d, STDOUT %s, STDERR %s" % \
    #      (process.returncode, out[0], out[1])

    if process.returncode == 0:
        move_job.Percent = 100

    # Queue up the result so that it gets executed in same thread as others.
    r = RequestEntry(-1, process_move_result,
                     (move_job, process.returncode, out[1]),
                     empty_cb, empty_cb, False)
    cfg.worker_q.put(r)


def add(command, reporting_job):
    # Create the thread, get it running and then add it to the list
    t = threading.Thread(target=move_execute,
                            name="thread: " + ' '.join(command),
                            args=(command, reporting_job))
    t.start()

    with _rlock:
        _thread_list.append(t)
