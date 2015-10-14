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
from utils import lv_obj_path_generate, thin_pool_obj_path_generate, \
    pv_obj_path_generate, vg_obj_path_generate, n
import dbus
import cfg
from cfg import VG_INTERFACE, MANAGER_INTERFACE
import cmdhandler
from request import RequestEntry
from loader import common
from lv import load_lvs
from state import State


def vgs_state_retrieve(selection):
    rc = []
    _vgs = cmdhandler.vg_retrieve(selection)
    vgs = sorted(_vgs, key=lambda vk: vk['vg_name'])
    for v in vgs:
        rc.append(
            VgState(v['vg_uuid'], v['vg_name'], v['vg_fmt'], n(v['vg_size']),
                    n(v['vg_free']), v['vg_sysid'], n(v['vg_extent_size']),
                    n(v['vg_extent_count']), n(v['vg_free_count']),
                    v['vg_profile'], n(v['max_lv']), n(v['max_pv']),
                    n(v['pv_count']), n(v['lv_count']), n(v['snap_count']),
                    n(v['vg_seqno']), n(v['vg_mda_count']),
                    n(v['vg_mda_free']), n(v['vg_mda_size']),
                    n(v['vg_mda_used_count']), v['vg_attr'], v['vg_tags']))
    return rc


def load_vgs(vg_specific=None, object_path=None, refresh=False):
    return common(vgs_state_retrieve, (Vg,), vg_specific, object_path, refresh)


# noinspection PyPep8Naming,PyUnresolvedReferences,PyUnusedLocal
class VgState(State):

    @property
    def lvm_id(self):
        return self.Name

    def identifiers(self):
        return (self.Uuid, self.Name)

    def _lv_paths_build(self, name):
        rc = []
        for lv in cmdhandler.lvs_in_vg(name):
            (lv_name, lv_attr, lv_uuid) = lv
            full_name = "%s/%s" % (self.Name, lv_name)

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

    def __init__(self, Uuid, Name, Fmt,
                 SizeBytes, FreeBytes, SysId, ExtentSizeBytes,
                 ExtentCount, FreeCount, Profile, MaxLv, MaxPv, PvCount,
                 LvCount, SnapCount, Seqno, MdaCount, MdaFree,
                 MdaSizeBytes, MdaUsedCount, attr, tags):
        utils.init_class_from_arguments(self, None)
        self.Pvs = self._pv_paths_build(Name)
        self.Lvs = self._lv_paths_build(Name)

    def create_dbus_object(self, path):
        if not path:
            path = cfg.om.get_object_path_by_lvm_id(
                self.Uuid, self.Name, vg_obj_path_generate)
        return Vg(path, self)


# noinspection PyPep8Naming
@utils.dbus_property('Uuid', 's')
@utils.dbus_property('Name', 's')
@utils.dbus_property('Fmt', 's')
@utils.dbus_property('SizeBytes', 't', 0)
@utils.dbus_property('FreeBytes', 't', 0)
@utils.dbus_property('SysId', 's')
@utils.dbus_property('ExtentSizeBytes', 't')
@utils.dbus_property('ExtentCount', 't')
@utils.dbus_property('FreeCount', 't')
@utils.dbus_property('Profile', 's')
@utils.dbus_property('MaxLv', 't')
@utils.dbus_property('MaxPv', 't')
@utils.dbus_property('PvCount', 't')
@utils.dbus_property('LvCount', 't')
@utils.dbus_property('SnapCount', 't')
@utils.dbus_property('Seqno', 't')
@utils.dbus_property('MdaCount', 't')
@utils.dbus_property('MdaFree', 't')
@utils.dbus_property('MdaSizeBytes', 't')
@utils.dbus_property('MdaUsedCount', 't')
class Vg(AutomatedProperties):
    DBUS_INTERFACE = VG_INTERFACE
    _Tags_type = "as"
    _Pvs_type = "ao"
    _Lvs_type = "ao"
    _Writeable_type = "b"
    _Readable_type = "b"
    _Exportable_type = 'b'
    _Partial_type = 'b'
    _AllocContiguous_type = 'b'
    _AllocCling_type = 'b'
    _AllocNormal_type = 'b'
    _AllocAnywhere_type = 'b'
    _Clustered_type = 'b'

    # noinspection PyUnusedLocal,PyPep8Naming
    def __init__(self, object_path, object_state):
        super(Vg, self).__init__(object_path, VG_INTERFACE, vgs_state_retrieve)
        self._object_path = object_path
        self.state = object_state

    def refresh_pvs(self, pv_list=None):
        """
        Refresh the state of the PVs for this vg given a PV object path
        """
        if not pv_list:
            pv_list = self.state.Pvs

        for p in pv_list:
            pv = cfg.om.get_by_path(p)
            pv.refresh()

    def refresh_lvs(self, lv_list=None, vg_name=None):
        """
        Refresh the state of the PVs for this vg given a PV object path
        """
        if not lv_list:
            lv_list = self.state.Lvs

        for i in lv_list:
            obj = cfg.om.get_by_path(i)

            if vg_name:
                obj.refresh(search_key="%s/%s" % (vg_name, obj.name))
            else:
                obj.refresh()

    @staticmethod
    def _rename(uuid, vg_name, new_name, rename_options):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            rc, out, err = cmdhandler.vg_rename(vg_name, new_name,
                                                rename_options)
            if rc == 0:

                # The refresh will fix up all the lookups for this object,
                # however the LVs will still have the wrong lookup entries.
                dbo.refresh(new_name)

                for lv in dbo.Lvs:
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
                         in_signature='sia{sv}', out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Rename(self, name, tmo, rename_options, cb, cbe):
        r = RequestEntry(tmo, Vg._rename,
                         (self.state.Uuid, self.state.lvm_id, name,
                          rename_options),
                         cb, cbe, False)
        cfg.worker_q.put(r)

    @staticmethod
    def _remove(uuid, vg_name, remove_options):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            # Remove the VG, if successful then remove from the model
            rc, out, err = cmdhandler.vg_remove(vg_name, remove_options)

            if rc == 0:
                # Remove data for associated LVs as it's gone
                for lv_path in dbo.Lvs:
                    lv = cfg.om.get_by_path(lv_path)
                    cfg.om.remove_object(lv, True)

                cfg.om.remove_object(dbo, True)
                # The vg is gone from LVM and from the dbus API, signal changes
                # in all the previously involved PVs as the usages have
                # changed.
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
                         in_signature='ia{sv}', out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Remove(self, tmo, remove_options, cb, cbe):
        r = RequestEntry(tmo, Vg._remove,
                         (self.state.Uuid, self.state.lvm_id, remove_options),
                         cb, cbe, False)
        cfg.worker_q.put(r)

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
                         in_signature='ia{sv}',
                         out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Change(self, tmo, change_options, cb, cbe):
        r = RequestEntry(tmo, Vg._change,
                         (self.state.Uuid, self.state.lvm_id, change_options),
                         cb, cbe, False)
        cfg.worker_q.put(r)

    @staticmethod
    def _reduce(uuid, vg_name, missing, pv_object_paths, reduce_options):
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

            rc, out, err = cmdhandler.vg_reduce(vg_name, missing, pv_devices,
                                                reduce_options)
            if rc == 0:
                original_pvs = dbo.state.Pvs
                dbo.refresh()
                dbo.refresh_pvs(original_pvs)
            else:
                raise dbus.exceptions.DBusException(
                    VG_INTERFACE, 'Exit code %s, stderr = %s' % (str(rc), err))
        else:
            raise dbus.exceptions.DBusException(
                VG_INTERFACE, 'VG with uuid %s and name %s not present!' %
                (uuid, vg_name))
        return '/'

    @dbus.service.method(dbus_interface=VG_INTERFACE,
                         in_signature='baoia{sv}',
                         out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Reduce(self, missing, pv_object_paths, tmo, reduce_options, cb, cbe):
        r = RequestEntry(tmo, Vg._reduce,
                         (self.state.Uuid, self.state.lvm_id, missing,
                          pv_object_paths, reduce_options), cb, cbe, False)
        cfg.worker_q.put(r)

    @staticmethod
    def _extend(uuid, vg_name, pv_object_paths, extend_options):
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
                rc, out, err = cmdhandler.vg_extend(vg_name, extend_devices,
                                                    extend_options)
                if rc == 0:
                    # This is a little confusing, because when we call
                    # dbo.refresh the current 'dbo' doesn't get updated,
                    # the object that gets called with the next dbus call will
                    # be the updated object so we need to manually append the
                    # object path of PVS and go see refresh method for more
                    # details.
                    current_pvs = list(dbo.Pvs)
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
                         in_signature='aoia{sv}', out_signature='o',
                         async_callbacks=('cb', 'cbe'))
    def Extend(self, pv_object_paths, tmo, extend_options, cb, cbe):
        r = RequestEntry(tmo, Vg._extend,
                         (self.state.Uuid, self.state.lvm_id, pv_object_paths,
                          extend_options),
                         cb, cbe, False)
        cfg.worker_q.put(r)

    @staticmethod
    def _lv_create_linear(uuid, vg_name, name, size_bytes,
                          thin_pool, create_options):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            rc, out, err = cmdhandler.vg_lv_create_linear(
                vg_name, create_options, name, size_bytes, thin_pool)

            if rc == 0:
                created_lv = "/"
                full_name = "%s/%s" % (vg_name, name)
                lvs = load_lvs([full_name])[0]
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
                         in_signature='stbia{sv}',
                         out_signature='(oo)',
                         async_callbacks=('cb', 'cbe'))
    def LvCreateLinear(self, name, size_bytes,
                       thin_pool, tmo, create_options, cb, cbe):
        r = RequestEntry(tmo, Vg._lv_create_linear,
                         (self.state.Uuid, self.state.lvm_id,
                          name, size_bytes, thin_pool, create_options),
                         cb, cbe)
        cfg.worker_q.put(r)

    @staticmethod
    def _lv_create_striped(uuid, vg_name, name, size_bytes, num_stripes,
                           stripe_size_kb, thin_pool, create_options):
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
                lvs = load_lvs([full_name])[0]
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
                         in_signature='stuubia{sv}',
                         out_signature='(oo)',
                         async_callbacks=('cb', 'cbe'))
    def LvCreateStriped(self, name, size_bytes, num_stripes,
                        stripe_size_kb, thin_pool, tmo, create_options,
                        cb, cbe):
        r = RequestEntry(tmo, Vg._lv_create_striped,
                         (self.state.Uuid, self.state.lvm_id, name,
                          size_bytes, num_stripes, stripe_size_kb, thin_pool,
                          create_options),
                         cb, cbe)
        cfg.worker_q.put(r)

    @staticmethod
    def _lv_create_mirror(uuid, vg_name, name, size_bytes,
                          num_copies, create_options):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            rc, out, err = cmdhandler.vg_lv_create_mirror(
                vg_name, create_options, name, size_bytes, num_copies)
            if rc == 0:
                created_lv = "/"
                full_name = "%s/%s" % (vg_name, name)
                lvs = load_lvs([full_name])[0]
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
                         in_signature='stuia{sv}',
                         out_signature='(oo)',
                         async_callbacks=('cb', 'cbe'))
    def LvCreateMirror(self, name, size_bytes, num_copies,
                       tmo, create_options, cb, cbe):
        r = RequestEntry(tmo, Vg._lv_create_mirror,
                         (self.state.Uuid, self.state.lvm_id, name,
                          size_bytes, num_copies,
                          create_options), cb, cbe)
        cfg.worker_q.put(r)

    @staticmethod
    def _lv_create_raid(uuid, vg_name, name, raid_type, size_bytes,
                        num_stripes, stripe_size_kb, thin_pool,
                        create_options):
        # Make sure we have a dbus object representing it
        dbo = cfg.om.get_by_uuid_lvm_id(uuid, vg_name)

        if dbo:
            rc, out, err = cmdhandler.vg_lv_create_raid(
                vg_name, create_options, name, raid_type, size_bytes,
                num_stripes, stripe_size_kb, thin_pool)
            if rc == 0:
                created_lv = "/"
                full_name = "%s/%s" % (vg_name, name)
                lvs = load_lvs([full_name])[0]
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
                         in_signature='sstuubia{sv}',
                         out_signature='(oo)',
                         async_callbacks=('cb', 'cbe'))
    def LvCreateRaid(self, name, raid_type, size_bytes,
                     num_stripes, stripe_size_kb, thin_pool, tmo,
                     create_options, cb, cbe):
        r = RequestEntry(tmo, Vg._lv_create_raid,
                         (self.state.Uuid, self.state.lvm_id, name,
                          raid_type, size_bytes, num_stripes, stripe_size_kb,
                          thin_pool, create_options), cb, cbe)
        cfg.worker_q.put(r)

    def _attribute(self, pos, ch):
        if self.state.attr[pos] == ch:
            return True
        return False

    @property
    def Tags(self):
        return utils.parse_tags(self.state.tags)

    @property
    def Pvs(self):
        return self.state.Pvs

    @property
    def Lvs(self):
        return self.state.Lvs

    @property
    def lvm_id(self):
        return self.state.lvm_id

    @property
    def Writeable(self):
        return self._attribute(0, 'w')

    @property
    def Readable(self):
        return self._attribute(0, 'r')

    @property
    def Resizeable(self):
        return self._attribute(1, 'z')

    @property
    def Exportable(self):
        return self._attribute(2, 'x')

    @property
    def Partial(self):
        return self._attribute(3, 'p')

    @property
    def AllocContiguous(self):
        return self._attribute(4, 'c')

    @property
    def AllocCling(self):
        return self._attribute(4, 'c')

    @property
    def AllocNormal(self):
        return self._attribute(4, 'n')

    @property
    def AllocAnywhere(self):
        return self._attribute(4, 'a')

    @property
    def Clustered(self):
        return self._attribute(5, 'c')
