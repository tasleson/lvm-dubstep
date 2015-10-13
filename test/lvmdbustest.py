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

BUSNAME = "com.redhat.lvmdbus1"
MANAGER_INT = BUSNAME + '.Manager'
MANAGER_OBJ = '/' + BUSNAME.replace('.', '/') + 'Manager'
PV_INT = BUSNAME + ".Pv"
VG_INT = BUSNAME + ".Vg"
LV_INT = BUSNAME + ".Lv"
THINPOOL_INT = BUSNAME + ".Thinpool"


class RemoteObject(object):

    def __init__(self, bus, object_path, interface, properties=None):
        self.object_path = object_path
        self.interface = interface

        self.method = dbus.Interface(bus.get_object(
            BUSNAME, self.object_path), self.interface)

        if not properties:
            #print 'Fetching properties'
            prop_fetch = dbus.Interface(bus.get_object(
                BUSNAME, self.object_path), 'org.freedesktop.DBus.Properties')
            properties = prop_fetch.GetAll(self.interface)
            #print str(properties)

        if properties:
            for kl, vl in properties.items():
                setattr(self, kl, vl)


def get_objects():
    rc = {MANAGER_INT: [], PV_INT: [], VG_INT: [], LV_INT: [],
          THINPOOL_INT: []}

    bus = dbus.SystemBus(mainloop=DBusGMainLoop())
    manager = dbus.Interface(bus.get_object(
        BUSNAME, "/com/redhat/lvmdbus1"),
        "org.freedesktop.DBus.ObjectManager")

    objects = manager.GetManagedObjects()

    for object_path, val in objects.items():
        for interface, props in val.items():
            o = RemoteObject(bus, object_path, interface, props)
            rc[interface].append(o)

    return rc, bus


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
            v.method.Remove(-1, {})

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
        pv_path = self.objs[MANAGER_INT][0].method.PvCreate(device, -1, {})[0]
        self.assertTrue(pv_path is not None and len(pv_path) > 0)
        return pv_path

    def _refresh(self):
        return self.objs[MANAGER_INT][0].method.Refresh()

    def test_refresh(self):
        rc = self._refresh()
        self.assertEqual(rc, 0)

    def test_version(self):
        rc = self.objs[MANAGER_INT][0].Version
        self.assertTrue(rc is not None and len(rc) > 0)
        self.assertEqual(self._refresh(), 0)

    def _vg_create(self):
        some_pv = self.objs[PV_INT][0]
        vg_name = 'test_vg_create'

        vg_path = self.objs[MANAGER_INT][0].method.VgCreate(
            vg_name,
            [some_pv.object_path],
            -1,
            {})
        self.assertTrue(vg_path is not None and len(vg_path) > 0)
        return vg_path[0], vg_name

    def test_vg_create(self):
        self._vg_create()
        self.assertEqual(self._refresh(), 0)

    def test_vg_delete(self):
        vg_path, vg_name = self._vg_create()
        vg = RemoteObject(self.bus, vg_path, VG_INT)
        vg.method.Remove(-1, {})
        self.assertEqual(self._refresh(), 0)

    def _pv_remove(self, pv):
        rc = pv.method.Remove(-1, {})
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
        return self.objs[MANAGER_INT][0].method.LookUpByLvmId(lvm_id)

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


if __name__ == '__main__':
    unittest.main()
