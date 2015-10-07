#!/usr/bin/env python2

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
# Copyright 2014-2015, Tony Asleson <tasleson@redhat.com>

import cfg
import objectmanager
import utils
from cfg import BASE_INTERFACE, BASE_OBJ_PATH, MANAGER_OBJ_PATH
import threading
import Queue
import traceback
import sys
import cmdhandler
import time
import signal
import dbus
import gobject
from fetch import load
from manager import Manager


class Lvm(objectmanager.ObjectManager):
    def __init__(self, object_path):
        super(Lvm, self).__init__(object_path, BASE_INTERFACE)


def process_request():
    while cfg.run.value != 0:
        try:
            req = cfg.worker_q.get(True, 5)
            req.run_cmd()
        except Queue.Empty:
            pass
        except Exception:
            traceback.print_exc(file=sys.stdout)
            pass


def signal_move_changes(obj_mgr):
    prev_jobs = {}

    def gen_signals(p, c):
        if p:
            #print 'PREV=', str(p)
            #print 'CURR=', str(c)

            for prev_k, prev_v in p.items():
                if prev_k in c:
                    if prev_v['src_dev'] == c[prev_k]['src_dev']:
                        prev_v['percent'] = c[prev_k]['percent']
                    else:
                        p[prev_k] = c[prev_k]

                    del c[prev_k]
                else:
                    state = p[prev_k]

                    del p[prev_k]

                    # Best guess is that the lv and the source & dest.
                    # PV state needs to be updated, need to verify.
                    obj_mgr.get_by_lvm_id(prev_k).refresh()
                    obj_mgr.get_by_lvm_id(state['src_dev']).refresh()
                    obj_mgr.get_by_lvm_id(state['dest_dev']).refresh()

            # Update previous to current
            p.update(c)

    while cfg.run.value != 0:
        try:
            cfg.kick_q.get(True, 5)
        except IOError:
            pass
        except Queue.Empty:
            pass

        while True:
            if cfg.run.value == 0:
                break

            cur_jobs = cmdhandler.pv_move_status()

            if cur_jobs:
                if not prev_jobs:
                    prev_jobs = cur_jobs
                else:
                    gen_signals(prev_jobs, cur_jobs)
            else:
                #Signal any that remain in running!
                gen_signals(prev_jobs, cur_jobs)
                prev_jobs = None
                break

            time.sleep(1)

    sys.exit(0)


def main():
    # Queue to wake up move monitor
    process_list = []

    start = time.time()

    # Install signal handlers
    for s in [signal.SIGHUP, signal.SIGINT]:
        try:
            signal.signal(s, utils.handler)
        except RuntimeError:
            pass

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    gobject.threads_init()
    dbus.mainloop.glib.threads_init()
    cfg.bus = dbus.SystemBus()
    # The base name variable needs to exist for things to work.
    # noinspection PyUnusedLocal
    base_name = dbus.service.BusName(BASE_INTERFACE, cfg.bus)
    cfg.om = Lvm(BASE_OBJ_PATH)
    cfg.om.register_object(Manager(MANAGER_OBJ_PATH))

    # Start up process to monitor moves
    process_list.append(
        threading.Thread(target=signal_move_changes, args=(cfg.om,)))

    # Using a thread to process requests.
    process_list.append(threading.Thread(target=process_request))

    load()
    cfg.loop = gobject.MainLoop()

    for process in process_list:
        process.damon = True
        process.start()

    end = time.time()
    print 'Service ready! total time= %.2f, lvm time= %.2f count= %d' % \
          (end - start, cmdhandler.total_time, cmdhandler.total_count)

    try:
        if cfg.run.value != 0:
            cfg.loop.run()

            for process in process_list:
                process.join()
    except KeyboardInterrupt:
        pass
    return 0
