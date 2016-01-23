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

# Try and minimize the refreshes we do.

import threading
from .request import RequestEntry
from . import cfg
from . import utils
from .fetch import load


_rlock = threading.RLock()
_count = 0


def handle_external_event(event, lvm_id, lvm_uuid, seq_no):
    utils.pprint("External event: '%s', '%s', '%s', '%s'" %
                 (event, lvm_id, lvm_uuid, str(seq_no)))
    event_complete()
    # Let's see if we have the VG and if the sequence numbers match, if
    # they do we have nothing to process (in theory)
    # We can try to be selective about what we re-fresh, but in reality
    # it takes just as long to selectively re-fresh as it does to grab
    # everything and let stuff sort itself out.
    if lvm_uuid and lvm_id:
        # If we are supplied with these, lets see if we need to update
        vg = cfg.om.get_by_uuid_lvm_id(lvm_uuid, lvm_id)
        if not (event == 'vg_update' and vg and vg.Seqno == seq_no):
            load(refresh=True, emit_signal=True)
    else:
        load(refresh=True, emit_signal=True)


def event_add(params):
    global _rlock
    global _count
    with _rlock:
        if _count == 0:
            _count += 1
            r = RequestEntry(-1, handle_external_event,
                             params, None, None, False)
            cfg.worker_q.put(r)


def event_complete():
    global _rlock
    global _count
    with _rlock:
        if _count > 0:
            _count -= 1
        return _count
