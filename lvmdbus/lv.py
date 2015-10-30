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
from automatedproperties import AutomatedProperties

import utils
from utils import vg_obj_path_generate, thin_pool_obj_path_generate
import dbus
import cmdhandler
import cfg
from cfg import LV_INTERFACE, MANAGER_INTERFACE, THIN_POOL_INTERFACE
from request import RequestEntry
from job import Job
from utils import lv_obj_path_generate, n, n32
from loader import common
from state import State


def lvs_state_retrieve(selection):
    rc = []
    _lvs = cmdhandler.lv_retrieve(selection)
    lvs = sorted(_lvs, key=lambda lk: lk['lv_name'])
    for l in lvs:
        rc.append(LvState(l['lv_uuid'], l['lv_name'],
                               l['lv_path'], n(l['lv_size']),
                               l['vg_name'],
                               l['vg_uuid'], l['pool_lv_uuid'],
                                l['pool_lv'], l['origin_uuid'], l['origin'],
                               n32(l['data_percent']), l['lv_attr'],
                               l['lv_tags']))
    return rc


def load_lvs(lv_name=None, object_path=None, refresh=False):
    # noinspection PyUnresolvedReferences
    return common(lvs_state_retrieve,
                  (lv_object_factory.lv_t, lv_object_factory.lv_pool_t),
                  lv_name, object_path, refresh)


# noinspection PyPep8Naming,PyUnresolvedReferences,PyUnusedLocal
class LvState(State):

    def _pv_devices(self, lvm_id):
        rc = []
        for pv in sorted(cmdhandler.lv_pv_devices(lvm_id)):
            (pv_name, pv_segs, pv_uuid) = pv
            pv_obj = cfg.om.get_object_path_by_lvm_id(
                pv_uuid, pv_name, gen_new=False)
            rc.append((pv_obj, pv_segs))

            for s in pv_segs:
                if s[2] not in self._segs:
                    self._segs.append(s[2])

        return dbus.Array(rc, signature="(oa(tts))")

    def vg_name_lookup(self):
        return cfg.om.get_by_path(self.Vg).Name

    @property
    def lvm_id(self):
        return "%s/%s" % (self.vg_name_lookup(), self.Name)

    def identifiers(self):
        return (self.Uuid, self.lvm_id)

    def __init__(self, Uuid, Name, Path, SizeBytes,
                     vg_name, vg_uuid, pool_lv_uuid, PoolLv,
                     origin_uuid, OriginLv, DataPercent, Attr, Tags):
        utils.init_class_from_arguments(self, None)
        self._segs = dbus.Array([], signature='s')

        self.Vg = cfg.om.get_object_path_by_lvm_id(
            Uuid, vg_name, vg_obj_path_generate)
        self.Devices = self._pv_devices(self.lvm_id)

        if PoolLv:
            self.PoolLv = cfg.om.get_object_path_by_lvm_id(
                pool_lv_uuid, '%s/%s' % (vg_name, PoolLv),
                thin_pool_obj_path_generate)
        else:
            self.PoolLv = '/'

        if OriginLv:
            self.OriginLv = \
                cfg.om.get_object_path_by_lvm_id(
                    origin_uuid, '%s/%s' % (vg_name, OriginLv),
                    vg_obj_path_generate)
        else:
            self.OriginLv = '/'

    @property
    def SegType(self):
        return self._segs

    def create_dbus_object(self, path):
        if not path:
            path = cfg.om.get_object_path_by_lvm_id(
                self.Uuid, self.lvm_id, lv_obj_path_generate)

        if self.Attr[0] != 't':
            return lv_object_factory(LV_INTERFACE, path, self)
        else:
            return lv_object_factory(THIN_POOL_INTERFACE, path, self)


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
    # noinspection PyPep8Naming
    @utils.dbus_property('Uuid', 's')
    @utils.dbus_property('Name', 's')
    @utils.dbus_property('Path', 's')
    @utils.dbus_property('SizeBytes', 't')
    @utils.dbus_property('DataPercent', 'u')
    @utils.dbus_property('SegType', 'as')
    @utils.dbus_property('Vg', 'o')
    @utils.dbus_property('OriginLv', 'o')
    @utils.dbus_property('PoolLv', 'o')
    @utils.dbus_property('Devices', "a(oa(tts))")
    class Lv(AutomatedProperties):
        DBUS_INTERFACE = interface_name
        _Tags_type = "as"
        _IsThinVolume_type = "b"
        _IsThinPool_type = "b"
        #_SegType_type = "as"

        # noinspection PyUnusedLocal,PyPep8Naming
        def __init__(self, object_path, object_state):

            super(Lv, self).__init__(object_path, interface_name,
                                     lvs_state_retrieve)
            utils.init_class_from_arguments(self)
            self.state = object_state

        def signal_vg_pv_changes(self):
            # Signal property changes...
            vg_obj = cfg.om.get_by_path(self.Vg)
            if vg_obj:
                vg_obj.refresh()

            for d in self.Devices:
                pv = cfg.om.get_by_path(d[0])
                if pv:
                    pv.refresh()

        def vg_name_lookup(self):
            return self.state.vg_name_lookup()

        @staticmethod
        def _remove(lv_uuid, lv_name, remove_options):
            # Make sure we have a dbus object representing it
            dbo = cfg.om.get_by_uuid_lvm_id(lv_uuid, lv_name)

            if dbo:
                # Remove the LV, if successful then remove from the model
                rc, out, err = cmdhandler.lv_remove(lv_name, remove_options)

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
                             in_signature='ia{sv}',
                             out_signature='o',
                             async_callbacks=('cb', 'cbe'))
        def Remove(self, tmo, remove_options, cb, cbe):
            r = RequestEntry(tmo, Lv._remove,
                             (self.Uuid, self.lvm_id, remove_options),
                             cb, cbe, False)
            cfg.worker_q.put(r)

        @staticmethod
        def _rename(lv_uuid, lv_name, new_name, rename_options):
            # Make sure we have a dbus object representing it
            dbo = cfg.om.get_by_uuid_lvm_id(lv_uuid, lv_name)

            if dbo:
                # Rename the logical volume
                rc, out, err = cmdhandler.lv_rename(lv_name, new_name,
                                                    rename_options)
                if rc == 0:
                    # Refresh the VG
                    vg_name = dbo.vg_name_lookup()

                    dbo.refresh("%s/%s" % (vg_name, new_name))
                    cfg.om.get_by_path(dbo.Vg).refresh()
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
                             in_signature='sia{sv}',
                             out_signature='o',
                             async_callbacks=('cb', 'cbe'))
        def Rename(self, name, tmo, rename_options, cb, cbe):
            r = RequestEntry(tmo, Lv._rename,
                             (self.Uuid, self.lvm_id, name, rename_options),
                             cb, cbe, False)
            cfg.worker_q.put(r)

        @property
        def Tags(self):
            return utils.parse_tags(self.state.Tags)

        @property
        def lvm_id(self):
            return self.state.lvm_id

        @property
        def IsThinVolume(self):
            return self.state.Attr[0] == 'V'

        @property
        def IsThinPool(self):
            return self.state.Attr[0] == 't'

        @dbus.service.method(dbus_interface=interface_name,
                             in_signature='o(tt)o(tt)a{sv}',
                             out_signature='o')
        def Move(self, pv_src_obj, pv_source_range, pv_dest_obj,
                 pv_dest_range, move_options):
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
                    job_obj = Job(self.lvm_id)
                    cfg.om.register_object(job_obj)
                    cfg.kick_q.put("wake up!")
                    return job_obj.dbus_object_path()
                else:
                    raise dbus.exceptions.DBusException(
                        interface_name,
                        'Exit code %s, stderr = %s' % (str(rc), err))
            else:
                raise dbus.exceptions.DBusException(
                    interface_name, 'pv_src_obj (%s) not found' % pv_src_obj)

        @staticmethod
        def _snap_shot(lv_uuid, lv_name, name, optional_size,
                       snapshot_options):
            # Make sure we have a dbus object representing it
            dbo = cfg.om.get_by_uuid_lvm_id(lv_uuid, lv_name)

            if dbo:
                # If you specify a size you get a 'thick' snapshot even if
                # it is a thin lv
                if not dbo.IsThinVolume:
                    if optional_size == 0:
                        # TODO: Should we pick a sane default or force user to
                        # make a decision?
                        space = dbo.SizeBytes / 80
                        remainder = space % 512
                        optional_size = space + 512 - remainder

                rc, out, err = cmdhandler.vg_lv_snapshot(
                    lv_name, snapshot_options, name, optional_size)
                if rc == 0:
                    full_name = "%s/%s" % (dbo.vg_name_lookup(), name)
                    lvs = load_lvs([full_name])[0]
                    for l in lvs:
                        cfg.om.register_object(l, True)
                        l.dbus_object_path()

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
            return '/'

        @dbus.service.method(dbus_interface=interface_name,
                             in_signature='sita{sv}',
                             out_signature='(oo)',
                             async_callbacks=('cb', 'cbe'))
        def Snapshot(self, name, tmo, optional_size, snapshot_options,
                     cb, cbe):
            r = RequestEntry(tmo, Lv._snap_shot,
                             (self.Uuid, self.lvm_id, name,
                              optional_size, snapshot_options), cb, cbe)
            cfg.worker_q.put(r)

        @staticmethod
        def _add_rm_tags(uuid, lv_name, tags_add, tags_del, tag_options):
            # Make sure we have a dbus object representing it
            dbo = cfg.om.get_by_uuid_lvm_id(uuid, lv_name)

            if dbo:

                rc, out, err = cmdhandler.lv_tag(lv_name, tags_add, tags_del,
                                                 tag_options)
                if rc == 0:
                    dbo.refresh()
                    return '/'
                else:
                    raise dbus.exceptions.DBusException(
                        MANAGER_INTERFACE,
                        'Exit code %s, stderr = %s' % (str(rc), err))

            else:
                raise dbus.exceptions.DBusException(
                    LV_INTERFACE, 'LV with uuid %s and name %s not present!' %
                    (uuid, lv_name))

        @dbus.service.method(dbus_interface=LV_INTERFACE,
                             in_signature='asia{sv}',
                             out_signature='o',
                             async_callbacks=('cb', 'cbe'))
        def TagsAdd(self, tags, tmo, tag_options, cb, cbe):
            r = RequestEntry(tmo, Lv._add_rm_tags,
                             (self.state.Uuid, self.state.lvm_id,
                              tags, None, tag_options),
                             cb, cbe, return_tuple=False)
            cfg.worker_q.put(r)

        @dbus.service.method(dbus_interface=LV_INTERFACE,
                             in_signature='asia{sv}',
                             out_signature='o',
                             async_callbacks=('cb', 'cbe'))
        def TagsDel(self, tags, tmo, tag_options, cb, cbe):
            r = RequestEntry(tmo, Lv._add_rm_tags,
                             (self.state.Uuid, self.state.lvm_id,
                              None, tags, tag_options),
                             cb, cbe, return_tuple=False)
            cfg.worker_q.put(r)

    # noinspection PyPep8Naming
    class LvPoolInherit(Lv):

        @staticmethod
        def _lv_create(lv_uuid, lv_name, name, size_bytes, create_options):
            # Make sure we have a dbus object representing it
            dbo = cfg.om.get_by_uuid_lvm_id(lv_uuid, lv_name)

            lv_created = '/'

            if dbo:
                rc, out, err = cmdhandler.lv_lv_create(
                    lv_name, create_options, name, size_bytes)
                if rc == 0:
                    full_name = "%s/%s" % (dbo.vg_name_lookup(), name)
                    lvs = load_lvs([full_name])[0]
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
                             in_signature='stia{sv}',
                             out_signature='(oo)',
                             async_callbacks=('cb', 'cbe'))
        def LvCreate(self, name, size_bytes, tmo, create_options, cb, cbe):
            r = RequestEntry(tmo, LvPoolInherit._lv_create,
                             (self.Uuid, self.lvm_id, name,
                              size_bytes, create_options), cb, cbe)
            cfg.worker_q.put(r)

    skip_create = False
    if len(args) == 1 and args[0] is None:
        skip_create = True

    if interface_name == LV_INTERFACE:
        if not hasattr(lv_object_factory, "lv_t"):
            lv_object_factory.lv_t = Lv

        if not skip_create:
            return lv_object_factory.lv_t(*args)
    elif interface_name == THIN_POOL_INTERFACE:
        if not hasattr(lv_object_factory, "lv_pool_t"):
            lv_object_factory.lv_pool_t = LvPoolInherit

        if not skip_create:
            return lv_object_factory.lv_pool_t(*args)
    else:
        raise Exception("Unsupported interface name %s" % (interface_name))


# Initialize the factory, yes this is a hack.  Still looking for something
# better for reducing code duplication and supporting inheritance when using
# method decorators.
lv_object_factory(LV_INTERFACE, None)
lv_object_factory(THIN_POOL_INTERFACE, None)
