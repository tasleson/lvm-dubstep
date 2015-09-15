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


from multiprocessing import Process, Queue, Lock, Value
from Queue import Empty
import dbus
import dbus.service
import dbus.mainloop.glib
import gobject
import os
import signal
import sys
import cmdhandler
import utils
from utils import n, n32
import itertools
import time

# Shared state variable across all processes
run = Value('i', 1)

#Debug
DEBUG = True

# Lock used by pprint
stdout_lock = Lock()

kick_q = Queue()

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


# Serializes access to stdout to prevent interleaved output
# @param msg    Message to output to stdout
# @return None
def pprint(msg):
    if DEBUG:
        stdout_lock.acquire()
        print "%d - %s" % (os.getpid(), msg)
        stdout_lock.release()


def handler(signum, frame):
    run.value = 0
    pprint('Signal handler called with signal %d' % signum)
    loop.quit()


counter = itertools.count()


def _next_id():
    return str(counter.next())


def pv_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return PV_OBJ_PATH + "/%s" % _next_id()


def vg_obj_path(vg_name):
    return VG_OBJ_PATH + "/%s" % vg_name


def lv_obj_path(lv_name):
    return LV_OBJ_PATH + "/%s" % lv_name


def thin_pool_path(pool_name):
    return THIN_POOL_PATH + "/%s" % pool_name


def job_obj_path(job_id):
    return JOB_OBJ_PATH + "/%s" % job_id


@utils.dbus_property('uuid', 's')               # PV UUID/pv_uuid
@utils.dbus_property('name', 's')               # PV/pv_name
@utils.dbus_property('fmt', 's')                # Fmt/pv_fmt
@utils.dbus_property('size_bytes', 't', 0)      # PSize/pv_size
@utils.dbus_property('free_bytes', 't', 0)      # PFree/pv_free
@utils.dbus_property('used_bytes', 't', 0)      # Used/pv_used
@utils.dbus_property('dev_size_bytes', 't', 0)  # DevSize/dev_size
@utils.dbus_property('mda_size_bytes', 't', 0)  # PMdaSize/pv_mda_size
@utils.dbus_property('mda_free_bytes', 't', 0)  # PMdaFree/pv_mda_free
@utils.dbus_property('ba_start', 't', 0)        # BA start/pv_ba_start
@utils.dbus_property('ba_size_bytes', 't', 0)   # BA size/pv_ba_size
@utils.dbus_property('pe_start', 't', 0)        # 1st PE/pe_start
@utils.dbus_property('pe_count', 't', 0)        # PE/pv_pe_count
@utils.dbus_property('pe_alloc_count', 't', 0)  # Alloc/pv_pe_alloc_count
@utils.dbus_property("vg", 'o', '/')            # Associated VG
class Pv(utils.AutomatedProperties):
    DBUS_INTERFACE = PV_INTERFACE

    # For properties that we need custom handlers we need these, otherwise
    # we won't get our introspection data
    _tags_type = "as"
    _pe_segments_type = "a(tt)"
    _exportable_type = "b"
    _allocatable_type = "b"
    _missing_type = "b"
    _lv_type = "a(oa(tt))"

    def __init__(self, c, object_path, object_manager, lvm_path, uuid, name,
                 fmt, size_bytes, free_bytes, used_bytes, dev_size_bytes,
                 mda_size_bytes, mda_free_bytes, ba_start, ba_size_bytes,
                 pe_start, pe_count, pe_alloc_count, attr, tags, vg_name):
        super(Pv, self).__init__(c, object_path, PV_INTERFACE, load_pvs)
        utils.init_class_from_arguments(self)
        self._pe_segments = cmdhandler.pv_segments(lvm_path)
        # Put this in object path format
        self._vg = vg_obj_path(self._vg_name)
        self._lv = cmdhandler.pv_contained_lv(self.lvm_id)

    @dbus.service.method(dbus_interface=PV_INTERFACE)
    def Remove(self):
        # Remove the PV, if successful then remove from the model
        rc, out, err = cmdhandler.pv_remove(self.lvm_id)

        if rc == 0:
            self._object_manager.remove_object(self, True)
        else:
            # Need to work on error handling, need consistent
            raise dbus.exceptions.DBusException(
                PV_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

    @dbus.service.method(dbus_interface=PV_INTERFACE, in_signature='t')
    def ReSize(self, new_size_bytes):

        rc, out, err = cmdhandler.pv_resize(self.lvm_id, new_size_bytes)
        if rc == 0:
            self.refresh()
        else:
            raise dbus.exceptions.DBusException(
                PV_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

    @dbus.service.method(dbus_interface=PV_INTERFACE,
                         in_signature='b')
    def AllocationEnabled(self, yes):
        rc, out, err = cmdhandler.pv_allocatable(self.lvm_id, yes)
        if rc == 0:
            self.refresh()
        else:
            raise dbus.exceptions.DBusException(
                PV_INTERFACE, 'Exit code %s, stderr = %s' % (str(rc), err))

    @property
    def tags(self):
        return utils.parse_tags(self._tags)

    @property
    def pe_segments(self):
        if len(self._pe_segments):
            return self._pe_segments
        return dbus.Array([], '(tt)')

    @property
    def exportable(self):
        if self._attr[1] == 'x':
            return True
        return False

    @property
    def allocatable(self):
        if self._attr[0] == 'a':
            return True
        return False

    @property
    def missing(self):
        if self._attr[2] == 'm':
            return True
        return False

    def object_path(self):
        return self._object_path

    @property
    def lvm_id(self):
        return self._lvm_path

    @property
    def lv(self):
        rc = []
        for lv in self._lv:
            rc.append((lv_obj_path(lv[0]), lv[1]))
        return dbus.Array(rc, signature="(oa(tt))")


@utils.dbus_property('uuid', 's')
@utils.dbus_property('name', 's')
@utils.dbus_property('fmt', 's')
@utils.dbus_property('size_bytes', 't', 0)
@utils.dbus_property('free_bytes', 't', 0)
@utils.dbus_property('sys_id', 's')
@utils.dbus_property('extent_size_bytes', 't')
@utils.dbus_property('extent_count', 't')
@utils.dbus_property('free_count', 't')
@utils.dbus_property('profile', 's')
@utils.dbus_property('max_lv', 't')
@utils.dbus_property('max_pv', 't')
@utils.dbus_property('pv_count', 't')
@utils.dbus_property('lv_count', 't')
@utils.dbus_property('snap_count', 't')
@utils.dbus_property('seqno', 't')
@utils.dbus_property('mda_count', 't')
@utils.dbus_property('mda_free', 't')
@utils.dbus_property('mda_size_bytes', 't')
@utils.dbus_property('mda_used_count', 't')
class Vg(utils.AutomatedProperties):
    DBUS_INTERFACE = VG_INTERFACE
    _tags_type = "as"
    _pvs_type = "ao"
    _lvs_type = "ao"
    _writeable_type = "b"
    _readable_type = "b"
    _exportable_type = 'b'
    _partial_type = 'b'
    _alloc_contiguous_type = 'b'
    _alloc_cling_type = 'b'
    _alloc_normal_type = 'b'
    _alloc_anywhere_type = 'b'
    _clustered_type = 'b'

    def __init__(self, c, object_path, object_manager, uuid, name, fmt,
                 size_bytes, free_bytes, sys_id, extent_size_bytes,
                 extent_count, free_count, profile, max_lv, max_pv, pv_count,
                 lv_count, snap_count, seqno, mda_count, mda_free,
                 mda_size_bytes, mda_used_count, attr, tags):
        super(Vg, self).__init__(c, object_path, VG_INTERFACE, load_vgs)
        utils.init_class_from_arguments(self)
        self._pv_in_vg = cmdhandler.pvs_in_vg(name)
        self._lv_in_vg = cmdhandler.lvs_in_vg(name)

    def _refresh_pvs(self, pv_list=None):
        """
        Refresh the state of the PVs for this vg given a PV object path
        """
        if not pv_list:
            pv_list = self.pvs

        for p in pv_list:
            pv = self._object_manager.get_by_path(p)
            pv.refresh()

    def _refresh_lvs(self, lv_list=None, vg_name=None):
        """
        Refresh the state of the PVs for this vg given a PV object path
        """
        if not lv_list:
            lv_list = self.lvs

        for i in lv_list:
            obj = self._object_manager.get_by_path(i)

            if vg_name:
                obj.refresh(search_key="%s/%s" % (vg_name, obj.name))
            else:
                obj.refresh()

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='s', out_signature='o')
    def Rename(self, name):
        # This is going to be a fairly expensive operation
        rc, out, err = cmdhandler.vg_rename(self.lvm_id, name)
        if rc == 0:
            # Refresh is a little more involved as we are changing it's path
            self.refresh(name)

            # Refresh all the PVs and LVs
            self._refresh_pvs()
            self._refresh_lvs(vg_name=name)

            return vg_obj_path(name)
        else:
            # Need to work on error handling, need consistent
            raise dbus.exceptions.DBusException(
                LV_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

    @dbus.service.method(dbus_interface=VG_INTERFACE)
    def Remove(self):
        # Remove the VG, if successful then remove from the model
        rc, out, err = cmdhandler.vg_remove(self.lvm_id)

        if rc == 0:
            self._object_manager.remove_object(self, True)

            # The vg is gone from LVM and from the dbus API, signal changes
            # in all the previously involved PVs
            self._refresh_pvs()

        else:
            # Need to work on error handling, need consistent
            raise dbus.exceptions.DBusException(
                VG_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

    # This should be broken into a number of different methods
    # instead of having one method that takes a hash for parameters.  Some of
    # the changes that vgchange does works on entire system, not just a
    # specfic vg, thus that should be in the Manager interface.
    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='a{sv}')
    def Change(self, change_options):
        rc, out, err = cmdhandler.vg_change(change_options, self.lvm_id)

        # To use an example with d-feet (Method input)
        # {"activate": __import__('gi.repository.GLib', globals(), locals(),
        # ['Variant']).Variant("s", "n")}

        if rc == 0:
            self.refresh()

            if 'activate' in change_options:
                for lv in self.lvs:
                    lv_obj = self._object_manager.get_by_path(lv)
                    lv_obj.refresh()
        else:
            raise dbus.exceptions.DBusException(
                VG_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='bao')
    def Reduce(self, missing, pv_object_paths):

        pv_devices = []

        # If pv_object_paths is not empty, then get the device paths
        if pv_object_paths and len(pv_object_paths) > 0:
            for pv_op in pv_object_paths:
                print('pv_op=', pv_op)
                pv = self._object_manager.get_by_path(pv_op)
                if pv:
                    pv_devices.append(pv.lvm_id)
                else:
                    raise dbus.exceptions.DBusException(
                        VG_INTERFACE, 'PV Object path not fount = %s!' % pv_op)

        rc, out, err = cmdhandler.vg_reduce(self.lvm_id, missing, pv_devices)
        if rc == 0:
            self.refresh()
            self._refresh_pvs()

        else:
            raise dbus.exceptions.DBusException(
                VG_INTERFACE, 'Exit code %s, stderr = %s' % (str(rc), err))

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='ao')
    def Extend(self, pv_object_paths):
        extend_devices = []

        for i in pv_object_paths:
            pv = self._object_manager.get_by_path(i)
            if pv:
                extend_devices.append(pv.lvm_id)
            else:
                raise dbus.exceptions.DBusException(
                    VG_INTERFACE, 'PV Object path not fount = %s!' % i)

        if len(extend_devices):
            rc, out, err = cmdhandler.vg_extend(self.lvm_id, extend_devices)
            if rc == 0:
                # This is a little confusing, because when we call self.refresh
                # the current 'self' doesn't get updated, the object that gets
                # called with the next dbus call will be the updated object
                # so we need to manually append the object path of PVS and go
                # see refresh method for more details.
                current_pvs = list(self.pvs)
                self.refresh()
                current_pvs.extend(pv_object_paths)
                self._refresh_pvs(current_pvs)
            else:
                raise dbus.exceptions.DBusException(
                    VG_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                VG_INTERFACE, 'No pv_object_paths provided!')

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='a{sv}st',
                         out_signature='o')
    def LvCreate(self, create_options, name, size_bytes):
        rc, out, err = cmdhandler.vg_lv_create(self.lvm_id, create_options,
                                               name, size_bytes)
        if rc == 0:
            full_name = "%s/%s" % (self.name, name)
            lvs = load_lvs(self._ap_c, self._object_manager, [full_name])
            for l in lvs:
                self._object_manager.register_object(l, True)

            # Refresh self and all included PVs
            self.refresh()
            self._refresh_pvs()

            return lv_obj_path(name)
        else:
            raise dbus.exceptions.DBusException(
                MANAGER_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='a{sv}stb',
                         out_signature='o')
    def LvCreateLinear(self, create_options, name, size_bytes,
                       thin_pool):
        rc, out, err = cmdhandler.vg_lv_create_linear(
            self.lvm_id, create_options, name, size_bytes, thin_pool)
        if rc == 0:
            full_name = "%s/%s" % (self.name, name)
            lvs = load_lvs(self._ap_c, self._object_manager, [full_name])
            for l in lvs:
                self._object_manager.register_object(l, True)

            # Refresh self and all included PVs
            self.refresh()
            self._refresh_pvs()

            return lv_obj_path(name)
        else:
            raise dbus.exceptions.DBusException(
                MANAGER_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='a{sv}stuub',
                         out_signature='o')
    def LvCreateStriped(self, create_options, name, size_bytes, num_stripes,
                        stripe_size_kb, thin_pool):
        rc, out, err = cmdhandler.vg_lv_create_striped(
            self.lvm_id, create_options, name, size_bytes, num_stripes,
            stripe_size_kb, thin_pool)
        if rc == 0:
            full_name = "%s/%s" % (self.name, name)
            lvs = load_lvs(self._ap_c, self._object_manager, [full_name])
            for l in lvs:
                self._object_manager.register_object(l, True)

            # Refresh self and all included PVs
            self.refresh()
            self._refresh_pvs()

            return lv_obj_path(name)
        else:
            raise dbus.exceptions.DBusException(
                MANAGER_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='a{sv}stu',
                         out_signature='o')
    def LvCreateMirror(self, create_options, name, size_bytes, num_copies):
        rc, out, err = cmdhandler.vg_lv_create_mirror(
            self.lvm_id, create_options, name, size_bytes, num_copies)
        if rc == 0:
            full_name = "%s/%s" % (self.name, name)
            lvs = load_lvs(self._ap_c, self._object_manager, [full_name])
            for l in lvs:
                self._object_manager.register_object(l, True)

            # Refresh self and all included PVs
            self.refresh()
            self._refresh_pvs()

            return lv_obj_path(name)
        else:
            raise dbus.exceptions.DBusException(
                MANAGER_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='a{sv}sstuub',
                         out_signature='o')
    def LvCreateRaid(self, create_options, name, raid_type, size_bytes,
                        num_stripes, stripe_size_kb, thin_pool):
        rc, out, err = cmdhandler.vg_lv_create_raid(
            self.lvm_id, create_options, name, raid_type, size_bytes,
            num_stripes, stripe_size_kb, thin_pool)
        if rc == 0:
            full_name = "%s/%s" % (self.name, name)
            lvs = load_lvs(self._ap_c, self._object_manager, [full_name])
            for l in lvs:
                self._object_manager.register_object(l, True)

            # Refresh self and all included PVs
            self.refresh()
            self._refresh_pvs()

            return lv_obj_path(name)
        else:
            raise dbus.exceptions.DBusException(
                MANAGER_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

    def _attribute(self, pos, ch):
        if self._attr[pos] == ch:
            return True
        return False

    @property
    def tags(self):
        return utils.parse_tags(self._tags)

    @property
    def pvs(self):
        rc = []
        for p in self._pv_in_vg:
            rc.append(self._object_manager.get_object_path_by_lvm_id(p))
        return dbus.Array(rc, signature='o')

    @property
    def lvs(self):
        # List of logical volumes that are created from this vg
        rc = []
        for lv in self._lv_in_vg:
            (lv_name, lv_attr) = lv[0], lv[1]

            if lv_attr[0] != 't':
                rc.append(lv_obj_path(lv_name))
            else:
                rc.append(thin_pool_path(lv_name))
        return dbus.Array(rc, signature='o')

    @property
    def lvm_id(self):
        return self._name

    @property
    def writeable(self):
        return self._attribute(0, 'w')

    @property
    def readable(self):
        return self._attribute(0, 'r')

    @property
    def resizeable(self):
        return self._attribute(1, 'z')

    @property
    def exportable(self):
        return self._attribute(2, 'x')

    @property
    def partial(self):
        return self._attribute(3, 'p')

    @property
    def alloc_contiguous(self):
        return self._attribute(4, 'c')

    @property
    def alloc_cling(self):
        return self._attribute(4, 'c')

    @property
    def alloc_normal(self):
        return self._attribute(4, 'n')

    @property
    def alloc_anywhere(self):
        return self._attribute(4, 'a')

    @property
    def clustered(self):
        return self._attribute(5, 'c')


@utils.dbus_property('uuid', 's')
@utils.dbus_property('name', 's')
@utils.dbus_property('path', 's')
@utils.dbus_property('size_bytes', 't')
@utils.dbus_property('pool_lv', 'o')
@utils.dbus_property('origin_lv', 'o')
@utils.dbus_property('data_percent', 'u')
@utils.dbus_property('segtype', 's')
class Lv(utils.AutomatedProperties):
    DBUS_INTERFACE = LV_INTERFACE
    _tags_type = "as"
    _vg_type = "o"
    _attr_type = "s"
    _devices_type = "a(oa(tt))"
    _is_thin_volume_type = "b"

    def __init__(self, c, object_path, object_manager,
                 uuid, name, path, size_bytes,
                 vg_name, pool_lv,
                 origin_lv, data_percent, attr, tags, segtype):
        super(Lv, self).__init__(c, object_path, LV_INTERFACE, load_lvs)
        utils.init_class_from_arguments(self)
        self._devices = cmdhandler.lv_pv_devices(self.lvm_id)

    def _signal_vg_pv_changes(self):
        # Signal property changes...
        vg_obj = self._object_manager.get_by_path(self.vg)
        if vg_obj:
            vg_obj.refresh()

        for d in self.devices:
            pv = self._object_manager.get_by_path(d[0])
            if pv:
                pv.refresh()

    @dbus.service.method(dbus_interface=LV_INTERFACE)
    def Remove(self):
        # Remove the LV, if successful then remove from the model
        rc, out, err = cmdhandler.lv_remove(self.lvm_id)

        if rc == 0:
            self._signal_vg_pv_changes()
            self._object_manager.remove_object(self, True)
        else:
            # Need to work on error handling, need consistent
            raise dbus.exceptions.DBusException(
                LV_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

    @dbus.service.method(dbus_interface=LV_INTERFACE,
                         in_signature='s',
                         out_signature='o')
    def Rename(self, name):
        # Rename the logical volume
        rc, out, err = cmdhandler.lv_rename(self.lvm_id, name)
        if rc == 0:
            # Refresh is a little more involved as we are changing it's path
            self.refresh("%s/%s" % (self._vg_name, name))
            self._signal_vg_pv_changes()
            return lv_obj_path(name)
        else:
            # Need to work on error handling, need consistent
            raise dbus.exceptions.DBusException(
                LV_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

    @property
    def tags(self):
        return utils.parse_tags(self._tags)

    @property
    def vg(self):
        return "%s/vg/%s" % (BASE_OBJ_PATH, self._vg_name)

    @property
    def attr(self):
        return self._attr

    @property
    def lvm_id(self):
        return "%s/%s" % (self._vg_name, self.name)

    @property
    def is_thin_volume(self):
        return self._attr[0] == 'V'

    @property
    def devices(self):
        rc = []
        for pv in self._devices:
            # We have an lvm device path, convert to dbus object and add.
            pv_obj = self._object_manager.get_object_path_by_lvm_id(pv[0])

            rc.append((pv_obj, pv[1]))
        return dbus.Array(rc, signature="(oa(tt))")

    @dbus.service.method(dbus_interface=LV_INTERFACE,
                         in_signature='a{sv}o(tt)o(tt)',
                         out_signature='o')
    def Move(self, move_options, pv_src_obj, pv_source_range, pv_dest_obj,
             pv_dest_range):
        pv_dest = None
        pv_src = self._object_manager.get_by_path(pv_src_obj)
        if pv_src:
            if pv_dest_obj != '/':
                pv_dest_t = self._object_manager.get_by_path(pv_dest_obj)
                if not pv_dest_t:
                    raise dbus.exceptions.DBusException(
                        LV_INTERFACE, 'pv_dest_obj (%s) not found' %
                        pv_src_obj)
                pv_dest = pv_dest_t.lvm_id

            rc, out, err = cmdhandler.pv_move_lv(
                move_options,
                self.lvm_id,
                pv_src.lvm_id,
                pv_source_range,
                pv_dest,
                pv_dest_range)

            if rc == 0:
                # Create job object for monitoring
                jobs = cmdhandler.pv_move_status()
                if self.lvm_id in jobs:
                    job_name = utils.md5(self.lvm_id + pv_src.lvm_id +
                                         str(time.time()))

                    job_obj = Job(self._c, job_obj_path(job_name),
                                  self._object_manager, self.lvm_id)
                    self._object_manager.register_object(job_obj)
                    kick_q.put("wake up!")
                    return job_obj.dbus_object_path()
            else:
                raise dbus.exceptions.DBusException(
                    LV_INTERFACE, 'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                LV_INTERFACE, 'pv_src_obj (%s) not found' % pv_src_obj)

    @dbus.service.method(dbus_interface=LV_INTERFACE,
                         in_signature='a{sv}st',
                         out_signature='o')
    def Snapshot(self, snapshot_options, name, optional_size):

        # If you specify a size you get a 'thick' snapshot even if it is a
        # thin lv
        if not self.is_thin_volume:
            if optional_size == 0:
                # TODO: Should we pick a sane default or force user to
                # make a decision?
                space = self.size_bytes / 80
                remainder = space % 512
                optional_size = space + 512 - remainder

        rc, out, err = cmdhandler.vg_lv_snapshot(self.lvm_id, snapshot_options,
                                                 name, optional_size)
        if rc == 0:

            full_name = "%s/%s" % (self._vg_name, name)
            lvs = load_lvs(self._ap_c, self._object_manager, [full_name])
            for l in lvs:
                self._object_manager.register_object(l, True)

            # Refresh self and all included PVs
            self.refresh()
            self._refresh_pvs()

            return lv_obj_path(name)
        else:
            raise dbus.exceptions.DBusException(
                MANAGER_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))


@utils.dbus_property('uuid', 's')
@utils.dbus_property('name', 's')
@utils.dbus_property('path', 's')
@utils.dbus_property('size_bytes', 't')
@utils.dbus_property('pool_lv', 'o')
@utils.dbus_property('origin_lv', 'o')
@utils.dbus_property('data_percent', 'u')
@utils.dbus_property('segtype', 's')
class LvPool(utils.AutomatedProperties):
    _tags_type = "as"
    _vg_type = "o"
    _attr_type = "s"
    _devices_type = "a(oa(tt))"

    DBUS_INTERFACE = THIN_POOL_INTERFACE
    """
    Thin pool LV will have a method to create a LV.
    """

    def __init__(self, c, object_path, object_manager,
                 uuid, name, path, size_bytes,
                 vg_name, pool_lv,
                 origin_lv, data_percent, attr, tags, segtype):
        super(LvPool, self).__init__(c, object_path, THIN_POOL_INTERFACE,
                                     load_lvs)
        utils.init_class_from_arguments(self)
        self._devices = cmdhandler.lv_pv_devices(self.lvm_id)

    @dbus.service.method(dbus_interface=THIN_POOL_INTERFACE)
    def Remove(self):
        # Remove the LV, if successful then remove from the model
        rc, out, err = cmdhandler.lv_remove(self.lvm_id)

        if rc == 0:
            self._object_manager.remove_object(self, True)
        else:
            # Need to work on error handling, need consistent
            raise dbus.exceptions.DBusException(
                LV_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

    @property
    def tags(self):
        return utils.parse_tags(self._tags)

    @property
    def vg(self):
        return "%s/vg/%s" % (BASE_OBJ_PATH, self._vg_name)

    @property
    def attr(self):
        return self._attr

    @property
    def lvm_id(self):
        return "%s/%s" % (self._vg_name, self.name)

    @property
    def devices(self):
        rc = []
        for pv in self._devices:
            pv_obj = self._object_manager.get_object_path_by_lvm_id(pv[0])
            rc.append((pv_obj, pv[1]))
        return dbus.Array(rc, signature="(oa(tt))")

    @dbus.service.method(dbus_interface=THIN_POOL_INTERFACE,
                         in_signature='a{sv}st',
                         out_signature='o')
    def LvCreate(self, create_options, name, size_bytes):
        rc, out, err = cmdhandler.lv_lv_create(self.lvm_id, create_options,
                                               name, size_bytes)
        if rc == 0:
            full_name = "%s/%s" % (self._vg_name, name)
            lvs = load_lvs(self._ap_c, self._object_manager, [full_name])
            for l in lvs:
                self._object_manager.register_object(l, True)

            return lv_obj_path(name)
        else:
            raise dbus.exceptions.DBusException(
                MANAGER_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))


def load_pvs(connection, obj_manager, device=None, object_path=None):
    pvs = cmdhandler.pv_retrieve(None, device)

    rc = []

    for p in pvs:
        p = Pv(connection, pv_obj_path_generate(object_path), obj_manager,
               p["pv_name"], p["pv_uuid"], p["pv_name"], p["pv_fmt"],
               n(p["pv_size"]),
               n(p["pv_free"]), n(p["pv_used"]), n(p["dev_size"]),
               n(p["pv_mda_size"]), n(p["pv_mda_free"]),
               long(p["pv_ba_start"]), n(p["pv_ba_size"]),
               n(p["pe_start"]), long(p["pv_pe_count"]),
               long(p["pv_pe_alloc_count"]),
               p["pv_attr"], p["pv_tags"], p["vg_name"])
        rc.append(p)
    return rc


def load_vgs(connection, obj_manager, vg_specific=None, object_path=None):
    vgs = cmdhandler.vg_retrieve(None, vg_specific)

    rc = []

    for v in vgs:
        vg = Vg(connection, vg_obj_path(v['vg_name']), obj_manager,
                v['vg_uuid'], v['vg_name'], v['vg_fmt'], n(v['vg_size']),
                n(v['vg_free']),
                v['vg_sysid'], n(v['vg_extent_size']), n(v['vg_extent_count']),
                n(v['vg_free_count']), v['vg_profile'], n(v['max_lv']),
                n(v['max_pv']), n(v['pv_count']),
                n(v['lv_count']), n(v['snap_count']),
                n(v['vg_seqno']), n(v['vg_mda_count']), n(v['vg_mda_free']),
                n(v['vg_mda_size']),
                n(v['vg_mda_used_count']), v['vg_attr'], v['vg_tags'])
        rc.append(vg)

    return rc


def load_lvs(connection, obj_manager, lv_name=None, object_path=None):
    lvs = cmdhandler.lv_retrieve(None, lv_name)

    rc = []

    for l in lvs:
        # Check to see if this LV is a thinpool!
        if l['lv_attr'][0] != 't':
            lv = Lv(connection, lv_obj_path(l['lv_name']),
                    obj_manager,
                    l['lv_uuid'],
                    l['lv_name'], l['lv_path'], n(l['lv_size']),
                    l['vg_name'], l['pool_lv'], l['origin'],
                    n32(l['data_percent']), l['lv_attr'], l['lv_tags'], l['segtype'])
        else:
            lv = LvPool(connection, thin_pool_path(l['lv_name']),
                        obj_manager,
                        l['lv_uuid'],
                        l['lv_name'], l['lv_path'], n(l['lv_size']),
                        l['vg_name'], l['pool_lv'], l['origin'],
                        n32(l['data_percent']), l['lv_attr'], l['lv_tags'], l['segtype'])

        rc.append(lv)
    return rc


def load(connection, obj_m):
    # Go through and load all the PVs, VGs and LVs
    for p in load_pvs(connection, obj_m):
        obj_m.register_object(p)

    for v in load_vgs(connection, obj_m):
        obj_m.register_object(v)

    for l in load_lvs(connection, obj_m):
        obj_m.register_object(l)


class Lvm(utils.ObjectManager):
    def __init__(self, connection, object_path):
        super(Lvm, self).__init__(connection, object_path,
                                  BASE_INTERFACE)


class Manager(utils.AutomatedProperties):
    DBUS_INTERFACE = MANAGER_INTERFACE

    def __init__(self, connection, object_path, object_manager):
        super(Manager, self).__init__(connection, object_path,
                                      MANAGER_INTERFACE)
        self._object_manager = object_manager

    @dbus.service.method(dbus_interface=MANAGER_INTERFACE,
                         in_signature='a{sv}s',
                         out_signature='o')
    def PvCreate(self, create_options, device):

        # Check to see if we are already trying to create a PV for an existing
        # PV
        pv = self._object_manager.get_object_path_by_lvm_id(device)
        if pv:
            raise dbus.exceptions.DBusException(
                MANAGER_INTERFACE, "PV Already exists!")

        created_pv = []
        rc, out, err = cmdhandler.pv_create(create_options, [device])
        if rc == 0:
            pvs = load_pvs(self._ap_c, self._object_manager, [device])
            for p in pvs:
                self._object_manager.register_object(p, True)
                created_pv = p.dbus_object_path()
        else:
            raise dbus.exceptions.DBusException(
                MANAGER_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

        return created_pv

    @dbus.service.method(dbus_interface=MANAGER_INTERFACE,
                         in_signature='a{sv}aos',
                         out_signature='o')
    def VgCreate(self, create_options, pv_object_paths, name):

        pv_devices = []

        for p in pv_object_paths:
            pv = self._object_manager.get_by_path(p)
            if pv:
                pv_devices.append(pv.name)
            else:
                raise dbus.exceptions.DBusException(
                    MANAGER_INTERFACE, 'object path = %s not found' % p)

        rc, out, err = cmdhandler.vg_create(create_options, pv_devices, name)
        created_vg = "/"

        if rc == 0:
            vgs = load_vgs(self._ap_c, self._object_manager, [name])
            for v in vgs:
                self._object_manager.register_object(v, True)
                created_vg = vg_obj_path(v.name)

            # For each PV that was involved in this VG create we need to
            # signal the property changes, make sure to do this *after* the
            # vg is available on the bus
            for p in pv_object_paths:
                pv = self._object_manager.get_by_path(p)
                pv.refresh()
        else:
            raise dbus.exceptions.DBusException(
                MANAGER_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))
        return created_vg

    @dbus.service.method(dbus_interface=MANAGER_INTERFACE)
    def Refresh(self):
        """
        Take all the objects we know about and go out and grab the latest
        more of a test method at the moment to make sure we are handling object
        paths correctly.
        """
        self._object_manager.refresh_all()


class Job(utils.AutomatedProperties):
    DBUS_INTERFACE = JOB_INTERFACE
    _percent_type = 'y'
    _is_complete_type = 'b'

    def __init__(self, c, object_path, object_manager, lv_name):
        super(Job, self).__init__(c, object_path, JOB_INTERFACE)
        utils.init_class_from_arguments(self)

    @property
    def percent(self):
        current = cmdhandler.pv_move_status()
        if self._lv_name in current:
            return current[self._lv_name]['percent']
        return 100

    @property
    def is_complete(self):
        current = cmdhandler.pv_move_status()
        if self._lv_name not in current:
            return True
        return False

    @dbus.service.method(dbus_interface=JOB_INTERFACE)
    def Remove(self):
        if self.is_complete:
            self._object_manager.remove_object(self, True)
        else:
            raise dbus.exceptions.DBusException(
                JOB_INTERFACE, 'Job is not complete!')


def signal_move_changes(obj_mgr):
    prev_jobs = {}
    cur_jobs = {}
    have_one = None

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

    while run.value != 0:
        try:
            kick_q.get(True, 5)
        except IOError:
            pass
        except Empty:
            pass

        while True:
            if run.value == 0:
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
                cur_jobs = None
                break

            time.sleep(1)

    sys.exit(0)

if __name__ == '__main__':
    # Queue to wake up move monitor
    process_list = []

    start = time.time()

    # Install signal handlers
    for s in [signal.SIGHUP, signal.SIGINT]:
        try:
            signal.signal(s, handler)
        except RuntimeError:
            pass

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    gobject.threads_init()
    dbus.mainloop.glib.threads_init()
    sys_bus = dbus.SystemBus()
    base_name = dbus.service.BusName(BASE_INTERFACE, sys_bus)
    lvm = Lvm(sys_bus, BASE_OBJ_PATH)
    lvm.register_object(Manager(sys_bus, MANAGER_OBJ_PATH, lvm))

    # Start up process to monitor moves
    process_list.append(Process(target=signal_move_changes, args=(lvm,)))

    load(sys_bus, lvm)
    loop = gobject.MainLoop()

    for process in process_list:
        process.damon = True
        process.start()

    end = time.time()
    print 'Service ready! total time= %.2f, lvm time= %.2f count= %d' % \
          (end - start, cmdhandler.total_time, cmdhandler.total_count)

    loop.run()

    for process in process_list:
        process.join()
        pprint("PID(%d), exit value= %d" % (process.pid, process.exitcode))
    sys.exit(0)
