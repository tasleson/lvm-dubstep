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

from .pv import load_pvs
from .vg import load_vgs
from .lv import load_lvs


def load(refresh=False):

    num_total_changes = 0

    # Go through and load all the PVs, VGs and LVs

    pvs, num_changes = load_pvs(refresh=refresh)
    num_total_changes += num_changes

    for p in pvs:
        cfg.om.register_object(p, refresh)

    vgs, num_changes = load_vgs(refresh=refresh)
    num_total_changes += num_changes

    for v in vgs:
        cfg.om.register_object(v, refresh)

    lvs, num_changes = load_lvs(refresh=refresh)
    num_total_changes += num_changes

    for l in lvs:
        cfg.om.register_object(l, refresh)

    return num_total_changes
