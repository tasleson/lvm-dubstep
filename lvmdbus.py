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


import multiprocessing
import Queue
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
import threading
import time
import ctypes
import traceback
import cfg

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


# Serializes access to stdout to prevent interleaved output
# @param msg    Message to output to stdout
# @return None
def pprint(msg):
    if DEBUG:
        stdout_lock.acquire()
        tid = ctypes.CDLL('libc.so.6').syscall(186)
        print "%d:%d - %s" % (os.getpid(), tid, msg)
        stdout_lock.release()


# noinspection PyUnusedLocal
def handler(signum, frame):
    run.value = 0
    pprint('Signal handler called with signal %d' % signum)
    loop.quit()


pv_id = itertools.count()
vg_id = itertools.count()
lv_id = itertools.count()
thin_id = itertools.count()
job_id = itertools.count()


def pv_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return PV_OBJ_PATH + "/%d" % pv_id.next()


def vg_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return VG_OBJ_PATH + "/%d" % vg_id.next()


def lv_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return LV_OBJ_PATH + "/%d" % lv_id.next()


def thin_pool_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return THIN_POOL_PATH + "/%d" % thin_id.next()


def job_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return JOB_OBJ_PATH + "/%d" % job_id.next()


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
    _vg_type = "o"

    def _lv_object_list(self, vg_name):
        rc = []
        if vg_name:
            for lv in sorted(cmdhandler.pv_contained_lv(self.lvm_id)):
                full_name = "%s/%s" % (vg_name, lv[0])
                segs = lv[1]
                attrib = lv[2]
                lv_uuid = lv[3]

                if attrib[0] == 't':
                    lv_path = cfg.om.get_object_path_by_lvm_id(
                        lv_uuid, full_name, thin_pool_obj_path_generate)
                else:
                    lv_path = cfg.om.get_object_path_by_lvm_id(
                        lv_uuid, full_name, lv_obj_path_generate)
                rc.append((lv_path, segs))
        return dbus.Array(rc, signature="(oa(tt))")

    # noinspection PyUnusedLocal
    def __init__(self, object_path, lvm_path, uuid, name,
                 fmt, size_bytes, free_bytes, used_bytes, dev_size_bytes,
                 mda_size_bytes, mda_free_bytes, ba_start, ba_size_bytes,
                 pe_start, pe_count, pe_alloc_count, attr, tags, vg_name,
                 vg_uuid):
        super(Pv, self).__init__(object_path, PV_INTERFACE, load_pvs)
        utils.init_class_from_arguments(self)
        self._pe_segments = cmdhandler.pv_segments(lvm_path)
        self._lv = self._lv_object_list(vg_name)

        if vg_name:
            self._vg_path = cfg.om.get_object_path_by_lvm_id(
                vg_uuid, vg_name, vg_obj_path_generate)
        else:
            self._vg_path = '/'

    @staticmethod
    def _remove(pv_uuid, pv_name):
        # Remove the PV, if successful then remove from the model
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(pv_uuid, pv_name)

        if dbo:
            rc, out, err = cmdhandler.pv_remove(pv_name)
            if rc == 0:
                cfg.om.remove_object(dbo, True)
            else:
                # Need to work on error handling, need consistent
                raise dbus.exceptions.DBusException(
                    PV_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                PV_INTERFACE, 'PV with uuid %s and name %s not present!' %
                (pv_uuid, pv_name))
        return '/'

    @dbus.service.method(dbus_interface=PV_INTERFACE,
                         in_signature='i',
                         out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Remove(self, tmo, cb, cbe):
        r = RequestEntry(tmo, Pv._remove,
                         (self.uuid, self.lvm_id),
                         cb, cbe, return_tuple=False)
        worker_q.put(r)

    @staticmethod
    def _resize(pv_uuid, pv_name, new_size_bytes):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(pv_uuid, pv_name)

        if dbo:
            rc, out, err = cmdhandler.pv_resize(pv_name, new_size_bytes)
            if rc == 0:
                dbo.refresh()
            else:
                raise dbus.exceptions.DBusException(
                    PV_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                PV_INTERFACE, 'PV with uuid %s and name %s not present!' %
                (pv_uuid, pv_name))
        return '/'

    @dbus.service.method(dbus_interface=PV_INTERFACE,
                         in_signature='ti',
                         out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def ReSize(self, new_size_bytes, tmo, cb, cbe):
        r = RequestEntry(tmo, Pv._resize,
                         (self.uuid, self.lvm_id, new_size_bytes), cb, cbe,
                         False)
        worker_q.put(r)

    @staticmethod
    def _allocation_enabled(pv_uuid, pv_name, yes_no):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(pv_uuid, pv_name)

        if dbo:
            rc, out, err = cmdhandler.pv_allocatable(pv_name, yes_no)
            if rc == 0:
                dbo.refresh()
            else:
                raise dbus.exceptions.DBusException(
                    PV_INTERFACE, 'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                PV_INTERFACE, 'PV with uuid %s and name %s not present!' %
                (pv_uuid, pv_name))
        return '/'

    @dbus.service.method(dbus_interface=PV_INTERFACE,
                         in_signature='bi',
                         out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def AllocationEnabled(self, yes, tmo, cb, cbe):
        r = RequestEntry(tmo, Pv._allocation_enabled,
                         (self.uuid, self.lvm_id, yes),
                         cb, cbe, False)
        worker_q.put(r)

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
        return self._lv

    @property
    def vg(self):
        return self._vg_path


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

    def _lv_paths_build(self, name):
        rc = []
        for lv in cmdhandler.lvs_in_vg(name):
            (lv_name, lv_attr, lv_uuid) = lv
            full_name = "%s/%s" % (self._name, lv_name)

            gen = lv_obj_path_generate
            if lv_attr[0] == 't':
                gen = thin_pool_obj_path_generate

            lv_path = cfg.om.get_object_path_by_lvm_id(
                lv_uuid, full_name, gen)
            rc.append(lv_path)
        return dbus.Array(rc, signature='o')

    @staticmethod
    def _pv_paths_build(name):
        rc = []
        for p in cmdhandler.pvs_in_vg(name):
            (pv_name, pv_uuid) = p
            rc.append(cfg.om.get_object_path_by_lvm_id(
                pv_uuid, pv_name, pv_obj_path_generate))
        return dbus.Array(rc, signature='o')

    # noinspection PyUnusedLocal
    def __init__(self, object_path, uuid, name, fmt,
                 size_bytes, free_bytes, sys_id, extent_size_bytes,
                 extent_count, free_count, profile, max_lv, max_pv, pv_count,
                 lv_count, snap_count, seqno, mda_count, mda_free,
                 mda_size_bytes, mda_used_count, attr, tags):
        super(Vg, self).__init__(object_path, VG_INTERFACE, load_vgs)
        utils.init_class_from_arguments(self)
        self._pv_in_vg = self._pv_paths_build(name)
        self._lv_in_vg = self._lv_paths_build(name)

    def refresh_pvs(self, pv_list=None):
        """
        Refresh the state of the PVs for this vg given a PV object path
        """
        if not pv_list:
            pv_list = self.pvs

        for p in pv_list:
            pv = cfg.om.get_by_path(p)
            pv.refresh()

    def refresh_lvs(self, lv_list=None, vg_name=None):
        """
        Refresh the state of the PVs for this vg given a PV object path
        """
        if not lv_list:
            lv_list = self.lvs

        for i in lv_list:
            obj = cfg.om.get_by_path(i)

            if vg_name:
                obj.refresh(search_key="%s/%s" % (vg_name, obj.name))
            else:
                obj.refresh()

    @staticmethod
    def _rename(uuid, vg_name, new_name):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            rc, out, err = cmdhandler.vg_rename(vg_name, new_name)
            if rc == 0:

                # The refresh will fix up all the lookups for this object,
                # however the LVs will still have the wrong lookup entries.
                dbo.refresh(new_name)

                for lv in dbo.lvs:
                    # This will fix the lookups, and the object state actually
                    # has an update as the path property is changing, but it's
                    # unfortunate that we need to go out and fetch all of these
                    # TODO: Change to some kind of batch operation where we do
                    # all with one lvs command instead of
                    # fetching one at a time
                    lv_obj = cfg.om.get_by_path(lv)
                    lv_obj.refresh()
            else:
                # Need to work on error handling, need consistent
                raise dbus.exceptions.DBusException(
                    VG_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                VG_INTERFACE, 'VG with uuid %s and name %s not present!' %
                (uuid, vg_name))
        return '/'

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='si', out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Rename(self, name, tmo, cb, cbe):
        r = RequestEntry(tmo, Vg._rename, (self.uuid, self.lvm_id, name), cb,
                         cbe, False)
        worker_q.put(r)

    @staticmethod
    def _remove(uuid, vg_name):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            # Remove the VG, if successful then remove from the model
            rc, out, err = cmdhandler.vg_remove(vg_name)

            if rc == 0:
                cfg.om.remove_object(dbo, True)
                # The vg is gone from LVM and from the dbus API, signal changes
                # in all the previously involved PVs
                dbo.refresh_pvs()
            else:
                # Need to work on error handling, need consistent
                raise dbus.exceptions.DBusException(
                    VG_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                VG_INTERFACE, 'VG with uuid %s and name %s not present!' %
                (uuid, vg_name))
        return '/'

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='i', out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Remove(self, tmo, cb, cbe):
        r = RequestEntry(tmo, Vg._remove,
                         (self.uuid, self.lvm_id),
                         cb, cbe, False)
        worker_q.put(r)

    @staticmethod
    def _change(uuid, vg_name, change_options):
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            rc, out, err = cmdhandler.vg_change(change_options, vg_name)

            # To use an example with d-feet (Method input)
            # {"activate": __import__('gi.repository.GLib', globals(),
            # locals(), ['Variant']).Variant("s", "n")}

            if rc == 0:
                dbo.refresh()

                if 'activate' in change_options:
                    for lv in dbo.lvs:
                        lv_obj = cfg.om.get_by_path(lv)
                        lv_obj.refresh()
            else:
                raise dbus.exceptions.DBusException(
                    VG_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                VG_INTERFACE, 'VG with uuid %s and name %s not present!' %
                (uuid, vg_name))
        return '/'

    # TODO: This should be broken into a number of different methods
    # instead of having one method that takes a hash for parameters.  Some of
    # the changes that vgchange does works on entire system, not just a
    # specfic vg, thus that should be in the Manager interface.
    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='a{sv}i',
                         out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Change(self, change_options, tmo, cb, cbe):
        r = RequestEntry(tmo, Vg._change,
                         (self.uuid, self.lvm_id, change_options),
                         cb, cbe, False)
        worker_q.put(r)

    @staticmethod
    def _reduce(uuid, vg_name, missing, pv_object_paths):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            pv_devices = []

            # If pv_object_paths is not empty, then get the device paths
            if pv_object_paths and len(pv_object_paths) > 0:
                for pv_op in pv_object_paths:
                    pv = cfg.om.get_by_path(pv_op)
                    if pv:
                        pv_devices.append(pv.lvm_id)
                    else:
                        raise dbus.exceptions.DBusException(
                            VG_INTERFACE,
                            'PV Object path not found = %s!' % pv_op)

            rc, out, err = cmdhandler.vg_reduce(vg_name, missing, pv_devices)
            if rc == 0:
                dbo.refresh()
                dbo.refresh_pvs()
            else:
                raise dbus.exceptions.DBusException(
                    VG_INTERFACE, 'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                VG_INTERFACE, 'VG with uuid %s and name %s not present!' %
                (uuid, vg_name))
        return '/'

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='baoi',
                         out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Reduce(self, missing, pv_object_paths, tmo, cb, cbe):
        r = RequestEntry(tmo, Vg._reduce,
                         (self.uuid, self.lvm_id, missing, pv_object_paths),
                         cb, cbe, False)
        worker_q.put(r)

    @staticmethod
    def _extend(uuid, vg_name, pv_object_paths):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            extend_devices = []

            for i in pv_object_paths:
                pv = cfg.om.get_by_path(i)
                if pv:
                    extend_devices.append(pv.lvm_id)
                else:
                    raise dbus.exceptions.DBusException(
                        VG_INTERFACE, 'PV Object path not found = %s!' % i)

            if len(extend_devices):
                rc, out, err = cmdhandler.vg_extend(vg_name, extend_devices)
                if rc == 0:
                    # This is a little confusing, because when we call
                    # dbo.refresh the current 'dbo' doesn't get updated,
                    # the object that gets called with the next dbus call will
                    # be the updated object so we need to manually append the
                    # object path of PVS and go see refresh method for more
                    # details.
                    current_pvs = list(dbo.pvs)
                    dbo.refresh()
                    current_pvs.extend(pv_object_paths)
                    dbo.refresh_pvs(current_pvs)
                else:
                    raise dbus.exceptions.DBusException(
                        VG_INTERFACE,
                        'Exit code %s, stderr = %s' % (str(rc), err))
            else:
                raise dbus.exceptions.DBusException(
                    VG_INTERFACE, 'No pv_object_paths provided!')
        else:
            raise dbus.exceptions.DBusException(
                VG_INTERFACE, 'VG with uuid %s and name %s not present!' %
                (uuid, vg_name))
        return '/'

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='aoi', out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Extend(self, pv_object_paths, tmo, cb, cbe):
        r = RequestEntry(tmo, Vg._extend,
                         (self.uuid, self.lvm_id, pv_object_paths),
                         cb, cbe, False)
        worker_q.put(r)

    @staticmethod
    def _lv_create_linear(uuid, vg_name, create_options, name, size_bytes,
                          thin_pool):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            rc, out, err = cmdhandler.vg_lv_create_linear(
                vg_name, create_options, name, size_bytes, thin_pool)

            if rc == 0:
                created_lv = "/"
                full_name = "%s/%s" % (vg_name, name)
                lvs = load_lvs([full_name])
                for l in lvs:
                    cfg.om.register_object(l, True)
                    created_lv = l.dbus_object_path()

                # Refresh self and all included PVs
                dbo.refresh()
                dbo.refresh_pvs()
            else:
                raise dbus.exceptions.DBusException(
                    MANAGER_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                VG_INTERFACE, 'VG with uuid %s and name %s not present!' %
                (uuid, vg_name))

        pprint("exiting _lv_create_linear %s" % (created_lv))
        return created_lv

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='a{sv}stbi',
                         out_signature='(oo)',
                         async_callbacks=('cb', 'cbe'))
    def LvCreateLinear(self, create_options, name, size_bytes,
                       thin_pool, tmo, cb, cbe):
        r = RequestEntry(tmo, Vg._lv_create_linear,
                         (self.uuid, self.lvm_id, create_options,
                          name, size_bytes, thin_pool),
                         cb, cbe)
        worker_q.put(r)

    @staticmethod
    def _lv_create_striped(uuid, vg_name, create_options, name, size_bytes,
                           num_stripes, stripe_size_kb, thin_pool):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            rc, out, err = cmdhandler.vg_lv_create_striped(vg_name,
                                                           create_options,
                                                           name, size_bytes,
                                                           num_stripes,
                                                           stripe_size_kb,
                                                           thin_pool)
            if rc == 0:
                created_lv = "/"
                full_name = "%s/%s" % (vg_name, name)
                lvs = load_lvs([full_name])
                for l in lvs:
                    cfg.om.register_object(l, True)
                    created_lv = l.dbus_object_path()

                # Refresh self and all included PVs
                dbo.refresh()
                dbo.refresh_pvs()
            else:
                raise dbus.exceptions.DBusException(
                    MANAGER_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                VG_INTERFACE, 'VG with uuid %s and name %s not present!' %
                (uuid, vg_name))

        return created_lv

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='a{sv}stuubi',
                         out_signature='(oo)',
                         async_callbacks=('cb', 'cbe'))
    def LvCreateStriped(self, create_options, name, size_bytes, num_stripes,
                        stripe_size_kb, thin_pool, tmo, cb, cbe):
        r = RequestEntry(tmo, Vg._lv_create_striped,
                         (self.uuid, self.lvm_id, create_options, name,
                          size_bytes, num_stripes, stripe_size_kb, thin_pool),
                         cb, cbe)
        worker_q.put(r)

    @staticmethod
    def _lv_create_mirror(uuid, vg_name, create_options, name, size_bytes,
                          num_copies):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            rc, out, err = cmdhandler.vg_lv_create_mirror(
                vg_name, create_options, name, size_bytes, num_copies)
            if rc == 0:
                created_lv = "/"
                full_name = "%s/%s" % (vg_name, name)
                lvs = load_lvs([full_name])
                for l in lvs:
                    cfg.om.register_object(l, True)
                    created_lv = l.dbus_object_path()

                # Refresh self and all included PVs
                dbo.refresh()
                dbo.refresh_pvs()
            else:
                raise dbus.exceptions.DBusException(
                    MANAGER_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))

        else:
            raise dbus.exceptions.DBusException(
                VG_INTERFACE, 'VG with uuid %s and name %s not present!' %
                (uuid, vg_name))

        return created_lv

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='a{sv}stui',
                         out_signature='(oo)',
                         async_callbacks=('cb', 'cbe'))
    def LvCreateMirror(self, create_options, name, size_bytes, num_copies,
                       tmo, cb, cbe):
        r = RequestEntry(tmo, Vg._lv_create_mirror,
                         (self.uuid, self.lvm_id, create_options,
                          name, size_bytes, num_copies), cb, cbe)
        worker_q.put(r)

    @staticmethod
    def _lv_create_raid(uuid, vg_name, create_options, name, raid_type,
                        size_bytes, num_stripes, stripe_size_kb, thin_pool):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            rc, out, err = cmdhandler.vg_lv_create_raid(
                vg_name, create_options, name, raid_type, size_bytes,
                num_stripes, stripe_size_kb, thin_pool)
            if rc == 0:
                created_lv = "/"
                full_name = "%s/%s" % (vg_name, name)
                lvs = load_lvs([full_name])
                for l in lvs:
                    cfg.om.register_object(l, True)
                    created_lv = l.dbus_object_path()

                # Refresh self and all included PVs
                dbo.refresh()
                dbo.refresh_pvs()
            else:
                raise dbus.exceptions.DBusException(
                    MANAGER_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))

        else:
            raise dbus.exceptions.DBusException(
                VG_INTERFACE, 'VG with uuid %s and name %s not present!' %
                (uuid, vg_name))

        return created_lv

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='a{sv}sstuubi',
                         out_signature='(oo)',
                         async_callbacks=('cb', 'cbe'))
    def LvCreateRaid(self, create_options, name, raid_type, size_bytes,
                        num_stripes, stripe_size_kb, thin_pool, tmo, cb, cbe):
        r = RequestEntry(tmo, Vg._lv_create_raid,
                         (self.uuid, self.lvm_id, create_options, name,
                          raid_type, size_bytes, num_stripes, stripe_size_kb,
                          thin_pool), cb, cbe)
        worker_q.put(r)

    def _attribute(self, pos, ch):
        if self._attr[pos] == ch:
            return True
        return False

    @property
    def tags(self):
        return utils.parse_tags(self._tags)

    @property
    def pvs(self):
        return self._pv_in_vg

    @property
    def lvs(self):
        return self._lv_in_vg

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


def lv_object_factory(interface_name, *args):
    """
    We want to be able to inherit from a class to minimize code.  When you
    try to do this we get in a situation where we can't set the interface
    because it's a string in the decorator.  Thus you cannot use a class
    variable as 'self' doesn't exit yet.  Workaround is to do do a nested
    class within a factory so that we can pass the interface we want to
    create the object with.

    :param interface_name: Interface we want to associate with class
    :param args: Arguments to be passed to object constructor
    :return: Object instance that matches interface wanted.
    """
    @utils.dbus_property('uuid', 's')
    @utils.dbus_property('name', 's')
    @utils.dbus_property('path', 's')
    @utils.dbus_property('size_bytes', 't')
    @utils.dbus_property('data_percent', 'u')
    @utils.dbus_property('segtype', 's')
    @utils.dbus_property('vg', 'o', '/')
    @utils.dbus_property('origin_lv', 'o', '/')
    @utils.dbus_property('pool_lv', 'o', '/')
    @utils.dbus_property('devices', "a(oa(tt))",
                         dbus.Array([], signature="(oa(tt))"))
    @utils.dbus_property('attr', 's')
    class Lv(utils.AutomatedProperties):
        DBUS_INTERFACE = interface_name
        _tags_type = "as"
        _is_thin_volume_type = "b"

        @staticmethod
        def _pv_devices(lvm_id):
            rc = []
            for pv in sorted(cmdhandler.lv_pv_devices(lvm_id)):
                (pv_name, pv_segs, pv_uuid) = pv
                pv_obj = cfg.om.get_object_path_by_lvm_id(
                    pv_name, pv_uuid)
                rc.append((pv_obj, pv_segs))
            return dbus.Array(rc, signature="(oa(tt))")

        # noinspection PyUnusedLocal
        def __init__(self, object_path,
                     uuid, name, path, size_bytes,
                     vg_name, vg_uuid, pool_lv,
                     origin_lv, data_percent, attr, tags, segtype):

            super(Lv, self).__init__(object_path, interface_name, load_lvs)
            utils.init_class_from_arguments(self)

            self._vg = cfg.om.get_object_path_by_lvm_id(
                vg_uuid, vg_name, vg_obj_path_generate)

            self._devices = self._pv_devices(self.lvm_id)

            # When https://bugzilla.redhat.com/show_bug.cgi?id=1264190 is
            # completed, fix this to pass the pool_lv_uuid too
            if pool_lv:
                self._pool_lv = cfg.om.get_object_path_by_lvm_id(
                    None, '%s/%s' % (vg_name, pool_lv),
                    thin_pool_obj_path_generate)

            if origin_lv:
                self._origin_lv = \
                    cfg.om.get_object_path_by_lvm_id(
                        None, '%s/%s' % (vg_name, origin_lv),
                        vg_obj_path_generate)

        def vg_name_lookup(self):
            return cfg.om.get_by_path(self._vg).name

        def signal_vg_pv_changes(self):
            # Signal property changes...
            vg_obj = cfg.om.get_by_path(self.vg)
            if vg_obj:
                vg_obj.refresh()

            for d in self.devices:
                pv = cfg.om.get_by_path(d[0])
                if pv:
                    pv.refresh()

        @staticmethod
        def _remove(lv_uuid, lv_name):
            # Make sure we have a dbus object representing it
            dbo = cfg.om.get_by_uuid_lvm_id(lv_uuid, lv_name)

            if dbo:
                # Remove the LV, if successful then remove from the model
                rc, out, err = cmdhandler.lv_remove(lv_name)

                if rc == 0:
                    dbo.signal_vg_pv_changes()
                    cfg.om.remove_object(dbo, True)
                else:
                    # Need to work on error handling, need consistent
                    raise dbus.exceptions.DBusException(
                        interface_name,
                        'Exit code %s, stderr = %s' % (str(rc), err))
            else:
                raise dbus.exceptions.DBusException(
                    LV_INTERFACE, 'LV with uuid %s and name %s not present!' %
                    (lv_uuid, lv_name))
            return '/'

        @dbus.service.method(dbus_interface=interface_name,
                             in_signature='i',
                             out_signature='o',
                             async_callbacks=('cb', 'cbe'))
        def Remove(self, tmo, cb, cbe):
            r = RequestEntry(tmo, Lv._remove,
                             (self.uuid, self.lvm_id), cb, cbe, False)
            worker_q.put(r)

        @staticmethod
        def _rename(lv_uuid, lv_name, new_name):
            # Make sure we have a dbus object representing it
            dbo = cfg.om.get_by_uuid_lvm_id(lv_uuid, lv_name)

            if dbo:
                # Rename the logical volume
                rc, out, err = cmdhandler.lv_rename(lv_name, new_name)
                if rc == 0:
                    # Refresh the VG
                    vg_name = dbo.vg_name_lookup()

                    dbo.refresh("%s/%s" % (vg_name, new_name))
                    cfg.om.get_by_path(dbo.vg).refresh()
                else:
                    # Need to work on error handling, need consistent
                    raise dbus.exceptions.DBusException(
                        interface_name,
                        'Exit code %s, stderr = %s' % (str(rc), err))
            else:
                raise dbus.exceptions.DBusException(
                    LV_INTERFACE, 'LV with uuid %s and name %s not present!' %
                    (lv_uuid, lv_name))
            return '/'

        @dbus.service.method(dbus_interface=interface_name,
                             in_signature='si',
                             out_signature='o',
                             async_callbacks=('cb', 'cbe'))
        def Rename(self, name, tmo, cb, cbe):
            r = RequestEntry(tmo, Lv._rename,
                             (self.uuid, self.lvm_id, name), cb, cbe, False)
            worker_q.put(r)

        @property
        def tags(self):
            return utils.parse_tags(self._tags)

        @property
        def lvm_id(self):
            return "%s/%s" % (self.vg_name_lookup(), self.name)

        @property
        def is_thin_volume(self):
            return self._attr[0] == 'V'

        @dbus.service.method(dbus_interface=interface_name,
                             in_signature='a{sv}o(tt)o(tt)',
                             out_signature='o')
        def Move(self, move_options, pv_src_obj, pv_source_range, pv_dest_obj,
                 pv_dest_range):
            pv_dest = None
            pv_src = cfg.om.get_by_path(pv_src_obj)
            if pv_src:
                if pv_dest_obj != '/':
                    pv_dest_t = cfg.om.get_by_path(pv_dest_obj)
                    if not pv_dest_t:
                        raise dbus.exceptions.DBusException(
                            interface_name, 'pv_dest_obj (%s) not found' %
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
                        job_obj = Job(self.lvm_id)
                        cfg.om.register_object(job_obj)
                        kick_q.put("wake up!")
                        return job_obj.dbus_object_path()
                else:
                    raise dbus.exceptions.DBusException(
                        interface_name,
                        'Exit code %s, stderr = %s' % (str(rc), err))
            else:
                raise dbus.exceptions.DBusException(
                    interface_name, 'pv_src_obj (%s) not found' % pv_src_obj)

        @staticmethod
        def _snap_shot(lv_uuid, lv_name, snapshot_options, name,
                       optional_size):
            # Make sure we have a dbus object representing it
            dbo = cfg.om.get_by_uuid_lvm_id(lv_uuid, lv_name)

            if dbo:
                # If you specify a size you get a 'thick' snapshot even if
                # it is a thin lv
                if not dbo.is_thin_volume:
                    if optional_size == 0:
                        # TODO: Should we pick a sane default or force user to
                        # make a decision?
                        space = dbo.size_bytes / 80
                        remainder = space % 512
                        optional_size = space + 512 - remainder

                rc, out, err = cmdhandler.vg_lv_snapshot(
                    lv_name, snapshot_options, name, optional_size)
                if rc == 0:
                    snapshot_path = "/"
                    full_name = "%s/%s" % (dbo.vg_name_lookup(), name)
                    lvs = load_lvs([full_name])
                    for l in lvs:
                        cfg.om.register_object(l, True)
                        snapshot_path = l.dbus_object_path()

                    # Refresh self and all included PVs
                    dbo.refresh()
                    dbo.signal_vg_pv_changes()
                else:
                    raise dbus.exceptions.DBusException(
                        MANAGER_INTERFACE,
                        'Exit code %s, stderr = %s' % (str(rc), err))
            else:
                raise dbus.exceptions.DBusException(
                    LV_INTERFACE, 'LV with uuid %s and name %s not present!' %
                    (lv_uuid, lv_name))
            return snapshot_path

        @dbus.service.method(dbus_interface=interface_name,
                             in_signature='a{sv}sti',
                             out_signature='(oo)',
                             async_callbacks=('cb', 'cbe'))
        def Snapshot(self, snapshot_options, name, optional_size, tmo, cb,
                     cbe):
            r = RequestEntry(tmo, Lv._snap_shot,
                             (self.uuid, self.lvm_id, snapshot_options, name,
                              optional_size), cb, cbe)
            worker_q.put(r)

    class LvPoolInherit(Lv):

        @staticmethod
        def _lv_create(lv_uuid, lv_name, create_options, name, size_bytes):
            # Make sure we have a dbus object representing it
            dbo = cfg.om.get_by_uuid_lvm_id(lv_uuid, lv_name)

            lv_created = '/'

            if dbo:
                rc, out, err = cmdhandler.lv_lv_create(
                    lv_name, create_options, name, size_bytes)
                if rc == 0:
                    full_name = "%s/%s" % (dbo.vg_name_lookup(), name)
                    lvs = load_lvs([full_name])
                    for l in lvs:
                        cfg.om.register_object(l, True)
                        lv_created = l.dbus_object_path()
                else:
                    raise dbus.exceptions.DBusException(
                        MANAGER_INTERFACE,
                        'Exit code %s, stderr = %s' % (str(rc), err))
            else:
                raise dbus.exceptions.DBusException(
                    LV_INTERFACE, 'LV with uuid %s and name %s not present!' %
                    (lv_uuid, lv_name))
            return lv_created

        @dbus.service.method(dbus_interface=interface_name,
                             in_signature='a{sv}sti',
                             out_signature='(oo)',
                             async_callbacks=('cb', 'cbe'))
        def LvCreate(self, create_options, name, size_bytes, tmo, cb, cbe):
            r = RequestEntry(tmo, LvPoolInherit._lv_create,
                             (self.uuid, self.lvm_id, create_options, name,
                              size_bytes), cb, cbe)
            worker_q.put(r)

    # Without this we each object has a new 'type' when constructed, so
    # we save off the object and construct instances of it.
    if not hasattr(lv_object_factory, "lv_t"):
        lv_object_factory.lv_t = Lv
        lv_object_factory.lv_pool_t = LvPoolInherit

    if interface_name == LV_INTERFACE:
        return lv_object_factory.lv_t(*args)
    elif interface_name == THIN_POOL_INTERFACE:
        return lv_object_factory.lv_pool_t(*args)
    else:
        raise Exception("Unsupported interface name %s" % (interface_name))


def load_pvs(device=None, object_path=None):
    _pvs = cmdhandler.pv_retrieve(device)

    pvs = sorted(_pvs, key=lambda k: k['pv_name'])

    rc = []

    for p in pvs:

        if not object_path:
            object_path = cfg.om.get_object_path_by_lvm_id(
                p['pv_uuid'], p['pv_name'], pv_obj_path_generate)

        p = Pv(object_path,
               p["pv_name"], p["pv_uuid"], p["pv_name"], p["pv_fmt"],
               n(p["pv_size"]),
               n(p["pv_free"]), n(p["pv_used"]), n(p["dev_size"]),
               n(p["pv_mda_size"]), n(p["pv_mda_free"]),
               long(p["pv_ba_start"]), n(p["pv_ba_size"]),
               n(p["pe_start"]), long(p["pv_pe_count"]),
               long(p["pv_pe_alloc_count"]),
               p["pv_attr"], p["pv_tags"], p["vg_name"], p["vg_uuid"])
        rc.append(p)

        object_path = None
    return rc


def load_vgs(vg_specific=None, object_path=None):
    _vgs = cmdhandler.vg_retrieve(vg_specific)

    vgs = sorted(_vgs, key=lambda k: k['vg_name'])

    rc = []

    for v in vgs:
        if not object_path:
            object_path = cfg.om.get_object_path_by_lvm_id(
                v['vg_uuid'], v['vg_name'], vg_obj_path_generate)

        vg = Vg(object_path,
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
        object_path = None

    return rc


def load_lvs(lv_name=None, object_path=None):
    _lvs = cmdhandler.lv_retrieve(lv_name)

    lvs = sorted(_lvs, key=lambda k: k['lv_name'])

    rc = []

    for l in lvs:
        ident = "%s/%s" % (l['vg_name'], l['lv_name'])

        # Check to see if this LV is a thinpool!
        if l['lv_attr'][0] != 't':

            if not object_path:
                object_path = cfg.om.get_object_path_by_lvm_id(
                    l['lv_uuid'], ident, lv_obj_path_generate)

            lv = lv_object_factory(LV_INTERFACE, object_path,
                                   l['lv_uuid'], l['lv_name'],
                                   l['lv_path'], n(l['lv_size']), l['vg_name'],
                                   l['vg_uuid'], l['pool_lv'], l['origin'],
                                   n32(l['data_percent']), l['lv_attr'],
                                   l['lv_tags'], l['segtype'])
        else:

            if not object_path:
                object_path = cfg.om.get_object_path_by_lvm_id(
                    l['lv_uuid'], ident, thin_pool_obj_path_generate)

            lv = lv_object_factory(
                THIN_POOL_INTERFACE, object_path,
                l['lv_uuid'], l['lv_name'], l['lv_path'], n(l['lv_size']),
                l['vg_name'], l['vg_uuid'], l['pool_lv'], l['origin'],
                n32(l['data_percent']), l['lv_attr'], l['lv_tags'],
                l['segtype'])

        rc.append(lv)
        object_path = None
    return rc


def load():
    # Go through and load all the PVs, VGs and LVs
    for p in load_pvs():
        cfg.om.register_object(p)

    for v in load_vgs():
        cfg.om.register_object(v)

    for l in load_lvs():
        cfg.om.register_object(l)


class Lvm(utils.ObjectManager):
    def __init__(self, object_path):
        super(Lvm, self).__init__(object_path, BASE_INTERFACE)


class Manager(utils.AutomatedProperties):
    DBUS_INTERFACE = MANAGER_INTERFACE

    def __init__(self, object_path):
        super(Manager, self).__init__(object_path, MANAGER_INTERFACE)

    @staticmethod
    def _pv_create(create_options, device):

        # Check to see if we are already trying to create a PV for an existing
        # PV
        pv = cfg.om.get_object_path_by_lvm_id(
            device, device, None, False)
        if pv:
            raise dbus.exceptions.DBusException(
                MANAGER_INTERFACE, "PV Already exists!")

        created_pv = []
        rc, out, err = cmdhandler.pv_create(create_options, [device])
        if rc == 0:
            pvs = load_pvs([device])
            for p in pvs:
                cfg.om.register_object(p, True)
                created_pv = p.dbus_object_path()
        else:
            raise dbus.exceptions.DBusException(
                MANAGER_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))

        return created_pv

    @dbus.service.method(dbus_interface=MANAGER_INTERFACE,
                         in_signature='a{sv}si',
                         out_signature='(oo)',
                         async_callbacks=('cb', 'cbe'))
    def PvCreate(self, create_options, device, tmo, cb, cbe):
        r = RequestEntry(tmo, Manager._pv_create,
                         (create_options, device), cb, cbe)
        worker_q.put(r)

    @staticmethod
    def _create_vg(create_options, pv_object_paths, name):
        pv_devices = []

        for p in pv_object_paths:
            pv = cfg.om.get_by_path(p)
            if pv:
                pv_devices.append(pv.name)
            else:
                raise dbus.exceptions.DBusException(
                    MANAGER_INTERFACE, 'object path = %s not found' % p)

        rc, out, err = cmdhandler.vg_create(create_options, pv_devices, name)
        created_vg = "/"

        if rc == 0:
            vgs = load_vgs([name])
            for v in vgs:
                cfg.om.register_object(v, True)
                created_vg = v.dbus_object_path()

            # For each PV that was involved in this VG create we need to
            # signal the property changes, make sure to do this *after* the
            # vg is available on the bus
            for p in pv_object_paths:
                pv = cfg.om.get_by_path(p)
                pv.refresh()
        else:
            raise dbus.exceptions.DBusException(
                MANAGER_INTERFACE,
                'Exit code %s, stderr = %s' % (str(rc), err))
        return created_vg

    @dbus.service.method(dbus_interface=MANAGER_INTERFACE,
                         in_signature='a{sv}aosi',
                         out_signature='(oo)',
                         async_callbacks=('cb', 'cbe'))
    def VgCreate(self, create_options, pv_object_paths, name, tmo, cb, cbe):
        r = RequestEntry(tmo, Manager._create_vg,
                         (create_options, pv_object_paths, name),
                         cb, cbe)
        worker_q.put(r)

    @dbus.service.method(dbus_interface=MANAGER_INTERFACE)
    def Refresh(self):
        """
        Take all the objects we know about and go out and grab the latest
        more of a test method at the moment to make sure we are handling object
        paths correctly.
        """
        cfg.om.refresh_all()

    @dbus.service.method(dbus_interface=MANAGER_INTERFACE,
                         in_signature='s',
                         out_signature='o')
    def LookUpByLvmId(self, key):
        """
        Given a lvm id in one of the forms:

        /dev/sda
        some_vg
        some_vg/some_lv
        Oe1rPX-Pf0W-15E5-n41N-ZmtF-jXS0-Osg8fn

        return the object path in O(1) time.

        :return: Return the object path.  If object not found you will get '/'
        """
        p = cfg.om.get_object_path_by_lvm_id(
            key, key, gen_new=False)
        if p:
            return p
        return '/'

    @dbus.service.method(dbus_interface=MANAGER_INTERFACE,
                         in_signature='sss', out_signature='i')
    def ExternalEvent(self, lvm_uuid, lvm_id, event):
        print 'External event %s:%s:%s' % (lvm_uuid, lvm_id, event)
        # TODO Add this to a work queue and return
        return dbus.Int32(0)


class Job(utils.AutomatedProperties):
    DBUS_INTERFACE = JOB_INTERFACE
    _percent_type = 'y'
    _is_complete_type = 'b'
    _result_type = 'o'
    _get_error_type = '(is)'

    def __init__(self, lv_name):
        super(Job, self).__init__(job_obj_path_generate(), JOB_INTERFACE)
        self._lv_name = lv_name

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

    @property
    def get_error(self):
        if self.is_complete:
            return (0, '')
        else:
            return (-1, 'Job is not complete!')

    @dbus.service.method(dbus_interface=JOB_INTERFACE)
    def Remove(self):
        if self.is_complete:
            cfg.om.remove_object(self, True)
        else:
            raise dbus.exceptions.DBusException(
                JOB_INTERFACE, 'Job is not complete!')

    @property
    def result(self):
        return '/'


class AsyncJob(utils.AutomatedProperties):
    DBUS_INTERFACE = JOB_INTERFACE
    _percent_type = 'y'
    _is_complete_type = 'b'
    _result_type = 'o'
    _get_error_type = '(is)'

    def __init__(self, request):
        super(AsyncJob, self).__init__(job_obj_path_generate(),
                                       JOB_INTERFACE)
        self._request = request
        self._percent = 1

    @property
    def percent(self):
        return self._percent

    @property
    def is_complete(self):
        done = self._request.is_done()
        if done:
            self._percent = 100
        return done

    @property
    def get_error(self):
        if self.is_complete:
            (rc, error) = self._request.get_errors()
            return (rc, str(error))
        else:
            return (-1, 'Job is not complete!')

    @dbus.service.method(dbus_interface=JOB_INTERFACE)
    def Remove(self):
        if self.is_complete:
            cfg.om.remove_object(self, True)
            self._request = None
        else:
            raise dbus.exceptions.DBusException(
                JOB_INTERFACE, 'Job is not complete!')

    @property
    def result(self):
        return self._request.result()


def _request_timeout(r):
    r.timer_expired()


class RequestEntry(object):
    def __init__(self, tmo, method, arguments, cb, cb_error,
                 return_tuple=True):
        self.tmo = tmo
        self.method = method
        self.arguments = arguments
        self.cb = cb
        self.cb_error = cb_error

        self.timer_id = -1
        self.lock = threading.Lock()
        self.done = False
        self._result = None
        self._job = False
        self._rc = 0
        self._rc_error = None
        self._return_tuple = return_tuple

        if self.tmo == -1:
            # Client is willing to block forever
            pass
        elif tmo == 0:
            self._return_job()
        else:
            self.timer_id = gobject.timeout_add_seconds(
                tmo, _request_timeout, self)

    def _return_job(self):
        self._job = True
        job = AsyncJob(self)
        cfg.om.register_object(job, True)
        if self._return_tuple:
            self.cb(('/', job.dbus_object_path()))
        else:
            self.cb(job.dbus_object_path())

    def run_cmd(self):
        try:
            result = self.method(*self.arguments)
            self.register_result(result)
        except dbus.DBusException as de:
            # Use the request entry to return the result as the client may
            # have gotten a job by the time we hit an error
            self.register_error(-1, de)

    def is_done(self):
        with self.lock:
            rc = self.done
        return rc

    def get_errors(self):
        with self.lock:
            return (self._rc, self._rc_error)

    def result(self):
        with self.lock:
            if self.done:
                return self._result
            return '/'

    def _reg_ending(self, result, error_rc=0, error=None):
        with self.lock:
            self.done = True
            if self.timer_id != -1:
                # Try to prevent the timer from firing
                gobject.source_remove(self.timer_id)

            self._result = result
            self._rc = error_rc
            self._rc_error = error

            if not self._job:
                # We finished and there is no job, so return result or error
                # now!
                if error_rc == 0:
                    if self._return_tuple:
                        self.cb((result, '/'))
                    else:
                        self.cb(result)
                else:
                    self.cb_error(self._rc_error)

    def register_error(self, error_rc, error):
        self._reg_ending(None, error_rc, error)

    def register_result(self, result):
        self._reg_ending(result)

    def timer_expired(self):
        with self.lock:
            # Set the timer back to -1 as we will get a warning if we try
            # to remove a timer that doesn't exist
            self.timer_id = -1
            if not self.done:
                # Create dbus job object and return path to caller
                self._return_job()
            else:
                # The job is done, we have nothing to do
                pass

        return False


def process_request():
    while run.value != 0:
        try:
            req = worker_q.get(True, 5)
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

    while run.value != 0:
        try:
            kick_q.get(True, 5)
        except IOError:
            pass
        except Queue.Empty:
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
    cfg.bus = dbus.SystemBus()
    base_name = dbus.service.BusName(BASE_INTERFACE, cfg.bus)
    cfg.om = Lvm(BASE_OBJ_PATH)
    cfg.om.register_object(Manager(MANAGER_OBJ_PATH))

    # Start up process to monitor moves
    process_list.append(
        threading.Thread(target=signal_move_changes, args=(cfg.om,)))

    # Using a thread to process requests.
    process_list.append(threading.Thread(target=process_request))

    load()
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
    sys.exit(0)
