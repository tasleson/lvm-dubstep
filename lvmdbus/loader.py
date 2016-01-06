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

from . import cfg


def common(retrieve, o_type, search_keys,
                object_path, refresh, emit_signal):
    num_changes = 0
    existing_paths = []
    rc = []

    if search_keys:
        assert isinstance(search_keys, list)

    objects = retrieve(search_keys)

    # If we are doing a refresh we need to know what we have in memory, what's
    # in lvm and add those that are new and remove those that are gone!
    if refresh:
        existing_paths = cfg.om.object_paths_by_type(o_type)

    for o in objects:
        # Assume we need to add this one to dbus, unless we are refreshing
        # and it's already present
        return_object = True

        if refresh:
            # We are refreshing all the PVs from LVM, if this one exists
            # we need to refresh our state.
            dbus_object = cfg.om.get_by_uuid_lvm_id(*o.identifiers())

            if dbus_object:
                del existing_paths[dbus_object.dbus_object_path()]
                num_changes += dbus_object.refresh(object_state=o)
                return_object = False

        if return_object:
            dbus_object = o.create_dbus_object(object_path)
            cfg.om.register_object(dbus_object, emit_signal)
            rc.append(dbus_object)

        object_path = None

    if refresh:
        for k in list(existing_paths.keys()):
            cfg.om.remove_object(cfg.om.get_by_path(k), True)
            num_changes += 1

    num_changes += len(rc)

    return rc, num_changes
