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

from . import cfg
from . import objectmanager
from . import utils
from .cfg import BASE_INTERFACE, BASE_OBJ_PATH, MANAGER_OBJ_PATH
import threading
from . import cmdhandler
import time
import signal
import dbus
from . import lvmdb
# noinspection PyUnresolvedReferences
from gi.repository import GObject
from .fetch import load
from .manager import Manager
from .pvmover import pv_move_reaper
import traceback
import queue
import sys
from . import udevwatch
from .utils import log_debug
import argparse


class Lvm(objectmanager.ObjectManager):
    def __init__(self, object_path):
        super(Lvm, self).__init__(object_path, BASE_INTERFACE)


def process_request():
    while cfg.run.value != 0:
        try:
            req = cfg.worker_q.get(True, 5)
            log_debug("Running method: %s with args %s" %
                      (str(req.method), str(req.arguments)))
            req.run_cmd()
            log_debug("Complete ")
        except queue.Empty:
            pass
        except Exception:
            traceback.print_exc(file=sys.stdout)
            pass


def main():

    # Add simple command line handling
    parser = argparse.ArgumentParser()
    parser.add_argument("--udev", action='store_true',
                        help="Use udev for updating state", default=False,
                        dest='use_udev')

    args = parser.parse_args()

    # List of threads that we start up
    thread_list = []

    start = time.time()

    # Install signal handlers
    for s in [signal.SIGHUP, signal.SIGINT]:
        try:
            signal.signal(s, utils.handler)
        except RuntimeError:
            pass

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    GObject.threads_init()
    dbus.mainloop.glib.threads_init()
    cfg.bus = dbus.SystemBus()
    # The base name variable needs to exist for things to work.
    # noinspection PyUnusedLocal
    base_name = dbus.service.BusName(BASE_INTERFACE, cfg.bus)
    cfg.om = Lvm(BASE_OBJ_PATH)
    cfg.om.register_object(Manager(MANAGER_OBJ_PATH))

    cfg.load = load

    cfg.db = lvmdb.DataStore()

    # Start up thread to monitor pv moves
    thread_list.append(
        threading.Thread(target=pv_move_reaper, name="pv_move_reaper"))

    # Using a thread to process requests.
    thread_list.append(threading.Thread(target=process_request))

    load()
    cfg.loop = GObject.MainLoop()

    for process in thread_list:
        process.damon = True
        process.start()

    end = time.time()
    log_debug('Service ready! total time= %.2f, lvm time= %.2f count= %d' %
              (end - start, cmdhandler.total_time, cmdhandler.total_count))

    # Add udev watching
    if args.use_udev:
        log_debug('Utilizing udev to trigger updates')
        udevwatch.add()

    try:
        if cfg.run.value != 0:
            cfg.loop.run()

            if args.use_udev:
                udevwatch.remove()

            for process in thread_list:
                process.join()
    except KeyboardInterrupt:
        utils.handler(signal.SIGINT, None)
    return 0
