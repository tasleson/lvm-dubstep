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

import multiprocessing
import Queue
import itertools

# This is the global object manager
om = None

# This is the global bus connection
bus = None

# Shared state variable across all processes
run = multiprocessing.Value('i', 1)

#Debug
DEBUG = True

# Lock used by pprint
stdout_lock = multiprocessing.Lock()

kick_q = multiprocessing.Queue()
worker_q = Queue.Queue()

# Main event loop
loop = None


BASE_INTERFACE = 'com.redhat.lvm1'
PV_INTERFACE = BASE_INTERFACE + '.pv'
VG_INTERFACE = BASE_INTERFACE + '.vg'
LV_INTERFACE = BASE_INTERFACE + '.lv'
THIN_POOL_INTERFACE = BASE_INTERFACE + '.thinpool'
MANAGER_INTERFACE = BASE_INTERFACE + '.Manager'
JOB_INTERFACE = BASE_INTERFACE + '.Job'

BASE_OBJ_PATH = '/com/redhat/lvm1'
PV_OBJ_PATH = BASE_OBJ_PATH + '/pv'
VG_OBJ_PATH = BASE_OBJ_PATH + '/vg'
LV_OBJ_PATH = BASE_OBJ_PATH + '/lv'
THIN_POOL_PATH = BASE_OBJ_PATH + "/thinpool"
MANAGER_OBJ_PATH = BASE_OBJ_PATH + '/Manager'
JOB_OBJ_PATH = BASE_OBJ_PATH + '/Job'


# Counters for object path generation
pv_id = itertools.count()
vg_id = itertools.count()
lv_id = itertools.count()
thin_id = itertools.count()
job_id = itertools.count()
