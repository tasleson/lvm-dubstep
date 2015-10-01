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

import multiprocessing
import Queue

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
