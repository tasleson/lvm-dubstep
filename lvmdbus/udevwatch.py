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

import pyudev
from refresh import event_add
import cfg

observer = None


# noinspection PyUnusedLocal
def filter_event(action, device):
    # Filter for events of interest and add a request object to be processed
    # when appropriate.
    refresh = False

    if '.ID_FS_TYPE_NEW' in device:
        fs_type_new = device['.ID_FS_TYPE_NEW']

        if 'LVM' in fs_type_new:
            refresh = True
        elif fs_type_new == '':
            # Check to see if the device was one we knew about
            if 'DEVNAME' in device:
                found = cfg.om.get_by_lvm_id(device['DEVNAME'])
                if found:
                    refresh = True

    if 'DM_LV_NAME' in device:
        refresh = True

    if refresh:
        event_add(('udev', None, None, 0))


def add():
    global observer
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by('block')
    observer = pyudev.MonitorObserver(monitor, filter_event)
    observer.start()


def remove():
    global observer
    observer.stop()
    observer = None
