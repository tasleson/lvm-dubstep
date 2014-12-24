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
# Copyright 2014, Tony Asleson <tasleson@redhat.com>

from multiprocessing import Lock
import dbus
import dbus.service
import dbus.mainloop.glib
import gobject
import os
import signal
import sys
import cmdhandler
import utils


#Debug
DEBUG = True

# Lock used by pprint
stdout_lock = Lock()

# Main event loop
loop = None

PV_INTERFACE = 'com.redhat.lvm.pv'
MANAGER_INTERFACE = 'com.redhat.lvm.Manager'


# Serializes access to stdout to prevent interleaved output
# @param msg    Message to output to stdout
# @return None
def pprint(msg):
    if DEBUG:
        stdout_lock.acquire()
        print "%d - %s" % (os.getpid(), msg)
        stdout_lock.release()


def handler(signum, frame):
    pprint('Signal handler called with signal %d' % signum)
    loop.quit()


@utils.dbus_property('uuid', 's')
@utils.dbus_property('name', 's')
@utils.dbus_property('testing', 's', 'some default value')
class Pv(utils.AutomatedProperties):
    def __init__(self, conn, object_path, lvm_path, uuid, name):
        utils.AutomatedProperties.__init__(self, conn, object_path,
                                           PV_INTERFACE)
        self.c = conn
        self.o_path = object_path
        self.lvm_path = lvm_path
        self._name = name
        self._uuid = uuid

    @dbus.service.method(dbus_interface=PV_INTERFACE)
    def Remove(self):
        # Remove the PV, if successful then remove from the model
        rc, out, err = cmdhandler.pv_remove(self.lvm_path)

        if rc == 0:
            self.remove_from_connection(self.c, self.o_path)
        else:
            # Need to work on error handling, need consistent
            raise dbus.exceptions.DBusException(
                PV_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))


def load(connection):
    # Go through and load all the PVs, VGs and LVs
    pvs = cmdhandler.pv_retrieve(None)

    for p in pvs:
        id_str = p['PV UUID'].replace('-', '')
        p = Pv(connection, "/com/redhat/lvm/pv/%s" % id_str,
               p["PV"], p["PV UUID"], p["PV"])


class Manager(dbus.service.Object):

    def __init__(self, connection, object_path):
        dbus.service.Object.__init__(self, connection, object_path)

    @dbus.service.method(dbus_interface=MANAGER_INTERFACE,
                         in_signature='a{sv}as')
    def PvCreate(self, create_options, devices):
        # No op at the moment
        pass

if __name__ == '__main__':

    # Install signal handlers
    for s in [signal.SIGHUP, signal.SIGINT]:
        try:
            signal.signal(s, handler)
        except RuntimeError:
            pass

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    sys_bus = dbus.SessionBus()
    base_name = dbus.service.BusName('com.redhat.lvm', sys_bus)
    Manager(sys_bus, '/com/redhat/lvm/Manager')

    load(sys_bus)
    loop = gobject.MainLoop()
    loop.run()
    sys.exit(0)