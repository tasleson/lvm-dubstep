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
# Copyright 2015, Tony Asleson <tasleson@redhat.com>

import dbus
from dbus.mainloop.glib import DBusGMainLoop
import unittest
import sys
import random
import string
import functools
import time


BUSNAME = "com.redhat.lvmdbus1"
MANAGER_INT = BUSNAME + '.Manager'
MANAGER_OBJ = '/' + BUSNAME.replace('.', '/') + 'Manager'
PV_INT = BUSNAME + ".Pv"
VG_INT = BUSNAME + ".Vg"
LV_INT = BUSNAME + ".Lv"
THINPOOL_INT = BUSNAME + ".Thinpool"
JOB_INT = BUSNAME + ".Job"


def rs(length, suffix):
    return ''.join(random.choice(string.ascii_lowercase)
                   for _ in range(length)) + suffix

bus = dbus.SystemBus(mainloop=DBusGMainLoop())


class RemoteObject(object):

    def _set_props(self, props=None):
        #print 'Fetching properties'
        if not props:
            prop_fetch = dbus.Interface(self.bus.get_object(
                BUSNAME, self.object_path), 'org.freedesktop.DBus.Properties')
            props = prop_fetch.GetAll(self.interface)

        if props:
            for kl, vl in props.items():
                setattr(self, kl, vl)

    def __init__(self, specified_bus, object_path, interface, properties=None):
        self.object_path = object_path
        self.interface = interface
        self.bus = specified_bus

        self.dbus_method = dbus.Interface(specified_bus.get_object(
            BUSNAME, self.object_path), self.interface)

        self._set_props(properties)

    def __getattr__(self, item):
        if hasattr(self.dbus_method, item):
            return functools.partial(self._wrapper, item)
        else:
            return functools.partial(self, item)

    def _wrapper(self, _method_name, *args, **kwargs):
        return getattr(self.dbus_method, _method_name)(*args, **kwargs)

    def update(self):
        self._set_props()


def get_objects():
    rc = {MANAGER_INT: [], PV_INT: [], VG_INT: [], LV_INT: [],
          THINPOOL_INT: [], JOB_INT: []}

    manager = dbus.Interface(bus.get_object(
        BUSNAME, "/com/redhat/lvmdbus1"),
        "org.freedesktop.DBus.ObjectManager")

    objects = manager.GetManagedObjects()

    for object_path, val in objects.items():
        for interface, props in val.items():
            o = RemoteObject(bus, object_path, interface, props)
            rc[interface].append(o)

    return rc, bus


def set_execution(lvmshell):
    lvm_manager = dbus.Interface(bus.get_object(
        BUSNAME, "/com/redhat/lvmdbus1/Manager"),
        "com.redhat.lvmdbus1.Manager")
    lvm_manager.UseLvmShell(lvmshell)


class TestDbusService(unittest.TestCase):
    def setUp(self):
        # Because of the sensitive nature of running LVM tests we will only
        # run if we have PVs and nothing else, so that we can be confident that
        # we are not mucking with someones data on their system
        self.objs, self.bus = get_objects()
        if len(self.objs[PV_INT]) == 0:
            print 'No PVs present exiting!'
            sys.exit(1)
        if len(self.objs[MANAGER_INT]) != 1:
            print 'Expecting a manager object!'
            sys.exit(1)

        if len(self.objs[VG_INT]) != 0:
            print 'Expecting no VGs to exist!'
            sys.exit(1)

        self.pvs = []
        for p in self.objs[PV_INT]:
            self.pvs.append(p.Name)

    def tearDown(self):
        # If we get here it means we passed setUp, so lets remove anything
        # and everything that remains, besides the PVs themselves
        self.objs, self.bus = get_objects()
        for v in self.objs[VG_INT]:
            #print "DEBUG: Removing VG= ", v.Uuid, v.Name
            v.Remove(-1, {})

        # Check to make sure the PVs we had to start exist, else re-create
        # them
        if len(self.pvs) != len(self.objs[PV_INT]):
            for p in self.pvs:
                found = False
                for pc in self.objs[PV_INT]:
                    if pc.Name == p:
                        found = True
                        break

                if not found:
                    print 'Re-creating PV=', p
                    self._pv_create(p)

    def _pv_create(self, device):
        pv_path = self.objs[MANAGER_INT][0].PvCreate(device, -1, {})[0]
        self.assertTrue(pv_path is not None and len(pv_path) > 0)
        return pv_path

    def _refresh(self):
        return self.objs[MANAGER_INT][0].Refresh()

    def test_refresh(self):
        rc = self._refresh()
        self.assertEqual(rc, 0)

    def test_version(self):
        rc = self.objs[MANAGER_INT][0].Version
        self.assertTrue(rc is not None and len(rc) > 0)
        self.assertEqual(self._refresh(), 0)

    def _vg_create(self, pv_paths=None):

        if not pv_paths:
            pv_paths = [self.objs[PV_INT][0].object_path]

        vg_name = rs(8, '_vg')

        vg_path = self.objs[MANAGER_INT][0].VgCreate(
            vg_name,
            pv_paths,
            -1,
            {})[0]
        self.assertTrue(vg_path is not None and len(vg_path) > 0)
        return RemoteObject(self.bus, vg_path, VG_INT)

    def test_vg_create(self):
        self._vg_create()
        self.assertEqual(self._refresh(), 0)

    def test_vg_delete(self):
        vg = self._vg_create()
        vg.Remove(-1, {})
        self.assertEqual(self._refresh(), 0)

    def _pv_remove(self, pv):
        rc = pv.Remove(-1, {})
        return rc

    def test_pv_remove_add(self):
        target = self.objs[PV_INT][0]

        # Remove the PV
        rc = self._pv_remove(target)
        self.assertTrue(rc == '/')
        self.assertEqual(self._refresh(), 0)

        # Add it back
        rc = self._pv_create(target.Name)[0]
        self.assertTrue(rc == '/')
        self.assertEqual(self._refresh(), 0)

    def _lookup(self, lvm_id):
        return self.objs[MANAGER_INT][0].LookUpByLvmId(lvm_id)

    def test_lookup_by_lvm_id(self):
        # For the moment lets just lookup what we know about which is PVs
        # When we start testing VGs and LVs we will test lookups for those
        # during those unit tests
        for p in self.objs[PV_INT]:
            rc = self._lookup(p.Name)
            self.assertTrue(rc is not None and rc != '/')

        # Search for something which doesn't exist
        rc = self._lookup('/dev/null')
        self.assertTrue(rc == '/')

    def test_vg_extend(self):
        # Create a VG
        self.assertTrue(len(self.objs[PV_INT]) >= 2)

        if len(self.objs[PV_INT]) >= 2:
            pv_initial = self.objs[PV_INT][0]
            pv_next = self.objs[PV_INT][1]

            vg = self._vg_create([pv_initial.object_path])
            path = vg.Extend([pv_next.object_path], -1, {})
            self.assertTrue(path == '/')
            self.assertEqual(self._refresh(), 0)

    # noinspection PyUnresolvedReferences
    def test_vg_reduce(self):
        self.assertTrue(len(self.objs[PV_INT]) >= 2)

        if len(self.objs[PV_INT]) >= 2:
            vg = self._vg_create(
                [self.objs[PV_INT][0].object_path,
                 self.objs[PV_INT][1].object_path])

            path = vg.Reduce(False, [vg.Pvs[0]], -1, {})
            self.assertTrue(path == '/')
            self.assertEqual(self._refresh(), 0)

    # noinspection PyUnresolvedReferences
    def test_vg_rename(self):
        vg = self._vg_create()
        path = vg.Rename('renamed_' + vg.Name, -1, {})
        self.assertTrue(path == '/')
        self.assertEqual(self._refresh(), 0)

    def _test_lv_create(self, method, params, vg, thinpool=False):
        lv = None
        path = method(*params)[0]

        self.assertTrue(vg)

        if path:
            if thinpool:
                lv = RemoteObject(self.bus, path, THINPOOL_INT)
            else:
                lv = RemoteObject(self.bus, path, LV_INT)
            # TODO verify object properties

        self.assertEqual(self._refresh(), 0)
        return lv

    def test_lv_create_linear(self):

        vg = self._vg_create()
        self._test_lv_create(vg.LvCreateLinear,
                             (rs(8, '_lv'), 1024 * 1024 * 4, False, -1, {}),
                             vg)

    def test_lv_create_striped(self):
        pv_paths = []
        for pp in self.objs[PV_INT]:
            pv_paths.append(pp.object_path)

        vg = self._vg_create(pv_paths)
        self._test_lv_create(vg.LvCreateStriped,
                             (rs(8, '_lv'), 1024 * 1024 * 4, 2, 8, False,
                              -1, {}), vg)

    def test_lv_create_mirror(self):
        pv_paths = []
        for pp in self.objs[PV_INT]:
            pv_paths.append(pp.object_path)

        vg = self._vg_create(pv_paths)
        self._test_lv_create(vg.LvCreateMirror,
                             (rs(8, '_lv'), 1024 * 1024 * 4, 2, -1, {}), vg)

    def test_lv_create_raid(self):
        pv_paths = []
        for pp in self.objs[PV_INT]:
            pv_paths.append(pp.object_path)

        vg = self._vg_create(pv_paths)
        self._test_lv_create(vg.LvCreateRaid,
                             (rs(8, '_lv'), 'raid4',
                              1024 * 1024 * 16, 2, 8, -1, {}), vg)

    def _create_lv(self, thinpool=False):
        pv_paths = []
        for pp in self.objs[PV_INT]:
            pv_paths.append(pp.object_path)

        vg = self._vg_create(pv_paths)
        return self._test_lv_create(
            vg.LvCreateLinear,
            (rs(8, '_lv'), 1024 * 1024 * 128, thinpool, -1, {}), vg, thinpool)

    def test_lv_create_thin_pool(self):
        self._create_lv(True)

    def test_lv_rename(self):
        # Rename a regular LV
        lv = self._create_lv()
        lv.Rename('renamed_' + lv.Name, -1, {})
        self.assertEqual(self._refresh(), 0)

    def test_lv_thinpool_rename(self):
        # Rename a thin pool
        thin_pool = self._create_lv(True)
        thin_pool.Rename('renamed_' + thin_pool.Name, -1, {})
        self.assertEqual(self._refresh(), 0)

    # noinspection PyUnresolvedReferences
    def test_lv_on_thin_pool_rename(self):
        # Rename a LV on a thin Pool
        thin_pool = self._create_lv(True)

        thin_path = thin_pool.LvCreate(
            rs(10, '_thin_lv'), 1024 * 1024 * 10, -1, {})[0]

        lv = RemoteObject(self.bus, thin_path, LV_INT)

        rc = lv.Rename('rename_test' + lv.Name, -1, {})
        self.assertTrue(rc == '/')
        self.assertEqual(self._refresh(), 0)

    def test_lv_remove(self):
        lv = self._create_lv()
        rc = lv.Remove(-1, {})
        self.assertTrue(rc == '/')
        self.assertEqual(self._refresh(), 0)

    def test_lv_snapshot(self):
        lv = self._create_lv()
        rc = lv.Snapshot('ss_' + lv.Name, -1, 0, {})[0]
        self.assertTrue(rc == '/')
        self.assertEqual(self._refresh(), 0)

    # noinspection PyUnresolvedReferences
    def _wait_for_job(self, j_path):
        import time
        rc = None
        while True:
            j = RemoteObject(self.bus, j_path, JOB_INT)
            if j.Complete:
                print 'Done!'
                self.assertTrue(j.Percent == 100)

                rc = j.Result
                j.Remove()

                break
            else:
                print 'Percentage = ', j.Percent

            if j.Wait(3):
                print 'Wait indicates we are done!'

        return rc

    def test_lv_move(self):
        lv = self._create_lv()

        pv_path_move = str(lv.Devices[0][0])

        print pv_path_move

        job = lv.Move(pv_path_move, (0, 0), '/', (0, 0), {})
        self._wait_for_job(job)
        self.assertEqual(self._refresh(), 0)

    def test_job_handling(self):
        pv_paths = []
        for pp in self.objs[PV_INT]:
            pv_paths.append(pp.object_path)

        vg_name = rs(8, '_vg')

        # Test getting a job right away
        vg_path, vg_job = self.objs[MANAGER_INT][0].VgCreate(
            vg_name, pv_paths,
            0, {})

        self.assertTrue(vg_path == '/')
        self.assertTrue(vg_job and len(vg_job) > 0)

        self._wait_for_job(vg_job)

    def _test_expired_timer(self):
        rc = False
        pv_paths = []
        for pp in self.objs[PV_INT]:
            pv_paths.append(pp.object_path)

        vg_name = rs(8, '_vg')

        # Test getting a job right away
        start = time.time()

        vg_path, vg_job = self.objs[MANAGER_INT][0].VgCreate(
            vg_name, pv_paths,
            1, {})

        end = time.time()

        self.assertTrue((end - float(start)) < 2.0)

        # Depending on how long it took we could finish either way
        if vg_path == '/':
            # We got a job
            self.assertTrue(vg_path == '/')
            self.assertTrue(vg_job and len(vg_job) > 0)

            vg_path = self._wait_for_job(vg_job)
            rc = True
        else:
            # It completed!
            self.assertTrue(vg_job == '/')

        # clean-up in case we need to try again
        vg = RemoteObject(self.bus, vg_path, VG_INT)
        vg.Remove(-1, {})

        return rc

    def test_job_handling_timer(self):

        yes = False

        print "\nNote: This test isn't guaranteed to pass..."

        for i in range(0, 20):
            yes = self._test_expired_timer()
            if yes:
                print 'Success!'
                break
            print 'Attempt (%d) failed, trying again...' % (i)

        self.assertTrue(yes)

    def test_pv_tags(self):
        pvs = []
        t = ['hello', 'world']

        pv_paths = []
        for pp in self.objs[PV_INT]:
            pv_paths.append(pp.object_path)

        vg = self._vg_create(pv_paths)

        # Get the PVs
        for p in vg.Pvs:
            pvs.append(RemoteObject(self.bus, p, PV_INT))

        rc = vg.PvTagsAdd(vg.Pvs, ['hello', 'world'], -1, {})
        self.assertTrue(rc == '/')

        for p in pvs:
            p.update()
            self.assertTrue(t == p.Tags)

        vg.PvTagsDel(vg.Pvs, t, -1, {})
        for p in pvs:
            p.update()
            self.assertTrue([] == p.Tags)

    def test_vg_tags(self):
        vg = self._vg_create()

        t = ['Testing', 'tags']

        vg.TagsAdd(t, -1, {})
        vg.update()
        self.assertTrue(t == vg.Tags)
        vg.TagsDel(t, -1, {})
        vg.update()
        self.assertTrue([] == vg.Tags)

    def test_lv_tags(self):
        vg = self._vg_create()
        lv = self._test_lv_create(
            vg.LvCreateLinear,
            (rs(8, '_lv'), 1024 * 1024 * 4, False, -1, {}),
            vg)

        t = ['Testing', 'tags']

        lv.TagsAdd(t, -1, {})
        lv.update()
        self.assertTrue(t == lv.Tags)
        lv.TagsDel(t, -1, {})
        lv.update()
        self.assertTrue([] == lv.Tags)

    def test_vg_allocation_policy_set(self):
        vg = self._vg_create()

        for p in ['anywhere', 'contiguous', 'cling', 'normal']:
            rc = vg.AllocationPolicySet(p, -1, {})
            self.assertEqual(rc, '/')
            vg.update()

            prop = getattr(vg, 'Alloc' + p.title())
            self.assertTrue(prop)

    def test_vg_max_pv(self):
        vg = self._vg_create()

        # BZ: https://bugzilla.redhat.com/show_bug.cgi?id=1280496
        # TODO: Add a test back for larger values here when bug is resolved
        for p in [0, 1, 10, 100, 100, 1024, 2**32 - 1]:
            rc = vg.MaxPvSet(p, -1, {})
            self.assertEqual(rc, '/')
            vg.update()
            self.assertTrue(vg.MaxPv == p, "Expected %s != Actual %s" %
                            (str(p), str(vg.MaxPv)))

    def test_vg_max_lv(self):
        vg = self._vg_create()

        # BZ: https://bugzilla.redhat.com/show_bug.cgi?id=1280496
        # TODO: Add a test back for larger values here when bug is resolved
        for p in [0, 1, 10, 100, 100, 1024, 2**32 - 1]:
            rc = vg.MaxLvSet(p, -1, {})
            self.assertEqual(rc, '/')
            vg.update()
            self.assertTrue(vg.MaxLv == p, "Expected %s != Actual %s" %
                            (str(p), str(vg.MaxLv)))

    def test_vg_uuid_gen(self):
        # TODO renable test case when
        # https://bugzilla.redhat.com/show_bug.cgi?id=1264169 gets fixed
        # This was tested with lvmetad disabled and we passed
        print "\nSkipping Vg.UuidGenerate until BZ: 1264169 resolved\n"

        if False:
            vg = self._vg_create()
            prev_uuid = vg.Uuid
            rc = vg.UuidGenerate(-1, {})
            self.assertEqual(rc, '/')
            vg.update()
            self.assertTrue(vg.Uuid != prev_uuid, "Expected %s != Actual %s" %
                            (vg.Uuid, prev_uuid))

    def test_vg_activate_deactivate(self):
        vg = self._vg_create()
        lv = self._test_lv_create(
            vg.LvCreateLinear,
            (rs(8, '_lv'), 1024 * 1024 * 4, False, -1, {}),
            vg)

        vg.update()

        vg.Deactivate(0, -1, {})
        self.assertEqual(self._refresh(), 0)

        vg.Activate(0, -1, {})
        self.assertEqual(self._refresh(), 0)

        # Try control flags
        for i in range(0, 5):
            vg.Activate(1 << i, -1, {})

if __name__ == '__main__':
    # Test forking & exec new each time
    set_execution(False)
    unittest.main()

    # Test lvm shell
    #print '\n *** Testing lvm shell *** \n'
    #set_execution(True)
    #unittest.main()
