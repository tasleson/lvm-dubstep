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
from .automatedproperties import AutomatedProperties

from . import utils
from .utils import vg_obj_path_generate, thin_pool_obj_path_generate
import dbus
from . import cmdhandler
from . import cfg
from .cfg import LV_INTERFACE, THIN_POOL_INTERFACE, SNAPSHOT_INTERFACE
from .request import RequestEntry
from .utils import lv_obj_path_generate, n, n32
from .loader import common
from .state import State
from . import pvmover


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
                               l['lv_tags'], l['lv_active']))
    return rc


def load_lvs(lv_name=None, object_path=None, refresh=False):
    # noinspection PyUnresolvedReferences
    return common(lvs_state_retrieve,
                  (Lv, LvPoolInherit, LvSnapShot),
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
                     origin_uuid, OriginLv, DataPercent, Attr, Tags, active):
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

        if self.Attr[0] == 't':
            return LvPoolInherit(path, self)
        elif self.OriginLv != '/':
            return LvSnapShot(path, self)
        else:
            return Lv(path, self)


# noinspection PyPep8Naming
@utils.dbus_property(LV_INTERFACE, 'Uuid', 's')
@utils.dbus_property(LV_INTERFACE, 'Name', 's')
@utils.dbus_property(LV_INTERFACE, 'Path', 's')
@utils.dbus_property(LV_INTERFACE, 'SizeBytes', 't')
@utils.dbus_property(LV_INTERFACE, 'DataPercent', 'u')
@utils.dbus_property(LV_INTERFACE, 'SegType', 'as')
@utils.dbus_property(LV_INTERFACE, 'Vg', 'o')
@utils.dbus_property(LV_INTERFACE, 'OriginLv', 'o')
@utils.dbus_property(LV_INTERFACE, 'PoolLv', 'o')
@utils.dbus_property(LV_INTERFACE, 'Devices', "a(oa(tts))")
class Lv(AutomatedProperties):
    _Tags_meta = ("as", LV_INTERFACE)
    _IsThinVolume_meta = ("b", LV_INTERFACE)
    _IsThinPool_meta = ("b", LV_INTERFACE)
    _Active_meta = ("b", LV_INTERFACE)

    # noinspection PyUnusedLocal,PyPep8Naming
    def __init__(self, object_path, object_state):
        super(Lv, self).__init__(object_path, lvs_state_retrieve)
        self.set_interface(LV_INTERFACE)
        self.state = object_state

    def signal_vg_pv_changes(self):
        # Signal property changes...
        vg_obj = cfg.om.get_by_path(self.Vg)
        vg_obj.refresh()
        vg_obj.refresh_pvs()

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
                    LV_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                LV_INTERFACE, 'LV with uuid %s and name %s not present!' %
                (lv_uuid, lv_name))
        return '/'

    @dbus.service.method(dbus_interface=LV_INTERFACE,
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
                dbo.signal_vg_pv_changes()

            else:
                # Need to work on error handling, need consistent
                raise dbus.exceptions.DBusException(
                    LV_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                LV_INTERFACE, 'LV with uuid %s and name %s not present!' %
                (lv_uuid, lv_name))
        return '/'

    @dbus.service.method(dbus_interface=LV_INTERFACE,
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

    @property
    def Active(self):
        return self.state.active == "active"

    @dbus.service.method(dbus_interface=LV_INTERFACE,
                         in_signature='o(tt)a(ott)ia{sv}',
                         out_signature='o')
    def Move(self, pv_src_obj, pv_source_range, pv_dests_and_ranges,
             tmo, move_options):
        return pvmover.move(LV_INTERFACE, self.lvm_id, pv_src_obj,
                            pv_source_range, pv_dests_and_ranges,
                            move_options, tmo)

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
                return_path = '/'
                full_name = "%s/%s" % (dbo.vg_name_lookup(), name)
                lvs = load_lvs([full_name])[0]
                for l in lvs:
                    cfg.om.register_object(l, True)
                    l.dbus_object_path()
                    return_path = l.dbus_object_path()

                # Refresh self and all included PVs
                dbo.refresh()
                dbo.signal_vg_pv_changes()
                return return_path
            else:
                raise dbus.exceptions.DBusException(
                    LV_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                LV_INTERFACE, 'LV with uuid %s and name %s not present!' %
                (lv_uuid, lv_name))

    @dbus.service.method(dbus_interface=LV_INTERFACE,
                         in_signature='stia{sv}',
                         out_signature='(oo)',
                         async_callbacks=('cb', 'cbe'))
    def Snapshot(self, name, optional_size, tmo, snapshot_options,
                 cb, cbe):
        r = RequestEntry(tmo, Lv._snap_shot,
                         (self.Uuid, self.lvm_id, name,
                          optional_size, snapshot_options), cb, cbe)
        cfg.worker_q.put(r)

    @staticmethod
    def _resize(lv_uuid, lv_name, new_size_bytes, pv_dests_and_ranges,
                resize_options):
        # Make sure we have a dbus object representing it
        pv_dests = []
        dbo = cfg.om.get_by_uuid_lvm_id(lv_uuid, lv_name)

        if dbo:
            # If we have PVs, verify them
            if len(pv_dests_and_ranges):
                for pr in pv_dests_and_ranges:
                    pv_dbus_obj = cfg.om.get_by_path(pr[0])
                    if not pv_dbus_obj:
                        raise dbus.exceptions.DBusException(
                            LV_INTERFACE,
                            'PV Destination (%s) not found' % pr[0])

                    pv_dests.append((pv_dbus_obj.lvm_id, pr[1], pr[2]))

            size_change = new_size_bytes - dbo.SizeBytes

            # Nothing to do
            if size_change == 0:
                return '/'

            rc, out, err = cmdhandler.lv_resize(dbo.lvm_id, size_change,
                                                pv_dests, resize_options)

            if rc == 0:
                # Refresh what's changed
                dbo.refresh()
                dbo.signal_vg_pv_changes()
                return "/"
            else:
                raise dbus.exceptions.DBusException(
                    LV_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                LV_INTERFACE, 'LV with uuid %s and name %s not present!' %
                (lv_uuid, lv_name))

    @dbus.service.method(dbus_interface=LV_INTERFACE,
                         in_signature='ta(ott)ia{sv}',
                         out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Resize(self, new_size_bytes, pv_dests_and_ranges, tmo,
               resize_options, cb, cbe):
        """
        Resize a LV
        :param new_size_bytes: The requested final size in bytes
        :param pv_dests_and_ranges: An array of pv object paths and src &
                                    dst. segment ranges
        :param tmo: -1 to wait forever, 0 to return job immediately, else
                    number of seconds to wait for operation to complete
                    before getting a job
        :param resize_options: key/value hash of options
        :param cb:  Used by framework not client facing API
        :param cbe: Used by framework not client facing API
        :return: '/' if complete, else job object path
        """
        r = RequestEntry(tmo, Lv._resize,
                         (self.Uuid, self.lvm_id, new_size_bytes,
                          pv_dests_and_ranges,
                          resize_options), cb, cbe, return_tuple=False)
        cfg.worker_q.put(r)

    @staticmethod
    def _lv_activate_deactivate(uuid, lv_name, activate, control_flags,
                                options):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, lv_name)

        if dbo:
            rc, out, err = cmdhandler.activate_deactivate(
                'lvchange', lv_name, activate, control_flags, options)
            if rc == 0:
                dbo.refresh()
                return '/'
            else:
                raise dbus.exceptions.DBusException(
                    LV_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                LV_INTERFACE, 'LV with uuid %s and name %s not present!' %
                (uuid, lv_name))

    @dbus.service.method(dbus_interface=LV_INTERFACE,
                         in_signature='tia{sv}',
                         out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Activate(self, control_flags, tmo, activate_options, cb, cbe):
        r = RequestEntry(tmo, Lv._lv_activate_deactivate,
                         (self.state.Uuid, self.state.lvm_id, True,
                          control_flags, activate_options),
                         cb, cbe, return_tuple=False)
        cfg.worker_q.put(r)

    # noinspection PyProtectedMember
    @dbus.service.method(dbus_interface=LV_INTERFACE,
                         in_signature='tia{sv}',
                         out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Deactivate(self, control_flags, tmo, activate_options, cb, cbe):
        r = RequestEntry(tmo, Lv._lv_activate_deactivate,
                         (self.state.Uuid, self.state.lvm_id, False,
                          control_flags, activate_options),
                         cb, cbe, return_tuple=False)
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
                    LV_INTERFACE,
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

    def __init__(self, object_path, object_state):
        super(LvPoolInherit, self).__init__(object_path, object_state)
        self.set_interface(THIN_POOL_INTERFACE)

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
                    LV_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                LV_INTERFACE, 'LV with uuid %s and name %s not present!' %
                (lv_uuid, lv_name))
        return lv_created

    @dbus.service.method(dbus_interface=THIN_POOL_INTERFACE,
                         in_signature='stia{sv}',
                         out_signature='(oo)',
                         async_callbacks=('cb', 'cbe'))
    def LvCreate(self, name, size_bytes, tmo, create_options, cb, cbe):
        r = RequestEntry(tmo, LvPoolInherit._lv_create,
                         (self.Uuid, self.lvm_id, name,
                          size_bytes, create_options), cb, cbe)
        cfg.worker_q.put(r)


# noinspection PyPep8Naming
class LvSnapShot(Lv):

    def __init__(self, object_path, object_state):
        super(LvSnapShot, self).__init__(object_path, object_state)
        self.set_interface(SNAPSHOT_INTERFACE)

    @staticmethod
    def _lv_merge(lv_uuid, lv_name, merge_options):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(lv_uuid, lv_name)

        if dbo:
            rc, out, err = cmdhandler.lv_merge(dbo.lvm_id, merge_options)
            if rc == 0:

                # Refresh the VG and the PVs and delete the LV that was just
                # merged
                dbo.signal_vg_pv_changes()
                cfg.om.remove_object(dbo, True)
                return "/"
            else:
                raise dbus.exceptions.DBusException(
                    LV_INTERFACE,
                    'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                LV_INTERFACE, 'LV with uuid %s and name %s not present!' %
                (lv_uuid, lv_name))

    @dbus.service.method(dbus_interface=SNAPSHOT_INTERFACE,
                         in_signature='ia{sv}',
                         out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Merge(self, tmo, merge_options, cb, cbe):
        r = RequestEntry(tmo, LvSnapShot._lv_merge,
                         (self.Uuid, self.lvm_id, merge_options), cb, cbe,
                         return_tuple=False)
        cfg.worker_q.put(r)
