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
# Copyright 2014-2015, Tony Asleson <tasleson@redhat.com>

import dbus
import xml.etree.ElementTree as Et
import hashlib
import traceback
import sys
import inspect
import cfg
import threading
import ctypes
import os


def md5(t):
    # noinspection PyUnresolvedReferences
    h = hashlib.md5()
    h.update(t)
    return h.hexdigest()


def is_numeric(s):
    try:
        long(s)
        return True
    except ValueError:
        return False


def rtype(dbus_type):
    """
    Decorator making sure that the decorated function returns a value of
    specified type.
    """

    def decorator(fn):
        def decorated(*args, **kwargs):
            return dbus_type(fn(*args, **kwargs))

        return decorated

    return decorator


# Field is expected to be a number, handle the corner cases when parsing
@rtype(dbus.UInt64)
def n(v):
    if not v:
        return 0L
    if v.endswith('B'):
        return long(v[:-1])
    return long(float(v))


@rtype(dbus.UInt32)
def n32(v):
    if not v:
        return 0
    if v.endswith('B'):
        return int(v[:-1])
    return int(float(v))


# noinspection PyProtectedMember
def init_class_from_arguments(obj_instance):
    for k, v in sys._getframe(1).f_locals.items():
        if k != 'self':
            nt = '_' + k

            # If the current attribute has a value, but the incoming does
            # not, don't overwrite it.  Otherwise the default values on the
            # property decorator don't work as expected.
            cur = getattr(obj_instance, nt, v)

            # print 'Init class %s = %s' % (nt, str(v))
            if not(cur and len(str(cur)) and (v is None or len(str(v))) == 0):
                setattr(obj_instance, nt, v)


def get_properties(f, interface=None):
    """
    Walks through an object instance or it's parent class(es) and determines
    which attributes are properties and if they were created to be used for
    dbus.
    :param f:   Object to inspect
    :param interface: The interface we are seeking properties for
    :return:    A tuple:
                0 = An array of dicts with the keys being: p_t, p_name,
                p_access(type, name, access)
                1 = Hash of property names and current value
    """
    result = []
    h_rc = {}

    for c in inspect.getmro(f.__class__):
        try:
            if interface is not None and c.DBUS_INTERFACE != interface:
                continue
        except AttributeError:
            continue

        h = vars(c)
        for p, value in h.iteritems():
            if isinstance(value, property):
                # We found a property, see if it has a metadata type
                key = attribute_type_name(p)
                if key in h:
                    access = ''
                    if getattr(f.__class__, p).fget:
                        access += 'read'
                    if getattr(f.__class__, p).fset:
                        access += 'write'

                    result.append(dict(p_t=getattr(f, key), p_name=p,
                                       p_access=access))
                    h_rc[p] = getattr(f, p)
    return result, h_rc


def get_object_property_diff(o_obj, n_obj):
    """
    Walk through each object properties and report what has changed and with
    the new values
    :param o_obj:   Old object
    :param n_obj:   New object
    :return: hash of properties that have changed and their new value
    """
    rc = {}

    if type(o_obj) != type(n_obj):
        raise Exception("Objects of different types! %s %s" %
                        (str(type(o_obj)), str(type(n_obj))))

    o_prop = get_properties(o_obj)[1]
    n_prop = get_properties(n_obj)[1]

    for k, v in o_prop.items():
        #print('Comparing %s:%s to %s:%s' %
        #      (k, str(o_prop[k]), k, str(n_prop[k])))
        if o_prop[k] != n_prop[k]:
            rc[k] = n_prop[k]
            # If the values aren't sorted the same, we get bogus differences.
            # Using this to tell the difference.
            print('DEBUG: get_object_property_diff %s:%s to %s:%s' %
                  (k, str(o_prop[k]), k, str(n_prop[k])))
    return rc


def add_properties(xml, interface, props):
    """
    Given xml that describes the interface, add property values to the XML
    for the specified interface.
    :param xml:         XML to edit
    :param interface:   Interface to add the properties too
    :param props:       Output from get_properties
    :return: updated XML string
    """
    root = Et.fromstring(xml)

    for c in root:
        # print c.attrib['name']
        if c.attrib['name'] == interface:
            for p in props:
                temp = '<property type="%s" name="%s" access="%s"/>\n' % \
                       (p['p_t'], p['p_name'], p['p_access'])
                c.append(Et.fromstring(temp))

            return Et.tostring(root, encoding='utf8')
    return xml


# noinspection PyTypeChecker
class AutomatedProperties(dbus.service.Object):
    """
    This class implements the needed interfaces for:
    org.freedesktop.DBus.Properties

    Other classes inherit from it to get the same behavior
    """

    DBUS_INTERFACE = ''

    def __init__(self, object_path, interface, search_method=None):
        dbus.service.Object.__init__(self, cfg.bus, object_path)
        self._ap_interface = interface
        self._ap_o_path = object_path
        self._ap_search_method = search_method

    def dbus_object_path(self):
        return self._ap_o_path

    def emit_data(self):
        props = {}

        for i in self.interface():
            props[i] = self.GetAll(i)

        return self._ap_o_path, props

    def interface(self, all_interfaces=False):
        rc = []
        if all_interfaces:
            rc = self._dbus_interface_table.keys()
        else:
            for k in self._dbus_interface_table.keys():
                if not k.startswith('org.freedesktop.DBus'):
                    rc.append(k)
        return rc

    # Properties
    # noinspection PyUnusedLocal
    @dbus.service.method(dbus_interface=dbus.PROPERTIES_IFACE,
                         in_signature='ss', out_signature='v')
    def Get(self, interface_name, property_name):
        value = getattr(self, property_name)
        # Note: If we get an exception in this handler we won't know about it,
        # only the side effect of no returned value!
        print 'Get (%s), type (%s), value(%s)' % \
              (property_name, str(type(value)), str(value))
        return value

    @dbus.service.method(dbus_interface=dbus.PROPERTIES_IFACE,
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface_name):
        if interface_name in self.interface():
            # Using introspection, lets build this dynamically
            return get_properties(self, interface_name)[1]
        raise dbus.exceptions.DBusException(
            self._ap_interface,
            'The object %s does not implement the %s interface'
            % (self.__class__, interface_name))

    @dbus.service.method(dbus_interface=dbus.PROPERTIES_IFACE,
                         in_signature='ssv')
    def Set(self, interface_name, property_name, new_value):
        setattr(self, property_name, new_value)
        self.PropertiesChanged(interface_name,
                               {property_name: new_value}, [])

    # As dbus-python does not support introspection for properties we will
    # get the autogenerated xml and then add our wanted properties to it.
    @dbus.service.method(dbus_interface=dbus.INTROSPECTABLE_IFACE,
                         out_signature='s')
    def Introspect(self):
        r = dbus.service.Object.Introspect(self, self._ap_o_path, cfg.bus)
        # Look at the properties in the class
        return add_properties(r, self._ap_interface, get_properties(self)[0])

    @dbus.service.signal(dbus_interface=dbus.PROPERTIES_IFACE,
                         signature='sa{sv}as')
    def PropertiesChanged(self, interface_name, changed_properties,
                          invalidated_properties):
        print('SIGNAL: PropertiesChanged(%s, %s, %s)' %
              (str(interface_name), str(changed_properties),
               str(invalidated_properties)))

    def refresh(self, search_key=None):
        """
        Take this object, go out and fetch the latest LVM copy and replace the
        one registered with dbus.  Not sure if there is a better way to do
        this, instead of resorting to removing the existing object and
        inserting a new one... One possible way to handle this is to separate
        the state of lvm from the dbus object representation.  Thus the
        dbus object would contain an object which represents lvm state, one
        that we could swap out whenever it was needed.

        WARNING: Once you call into this method, "self" is removed
        from the dbus API and thus you cannot call any dbus methods upon it.

        """
        num_changed = 0

        # If we can't do a lookup, bail now, this happens if we blindly walk
        # through all dbus objects as some don't have a search method, like
        # 'Manager' object.
        if not self._ap_search_method:
            return

        with cfg.om.locked():
            # We want the remove & subsequent add to be atomic, would be better
            # if we could move this into the object manager class itself...
            # The bigger question is we typically refresh a number of different
            # objects together, as part of a change.  As lvm does locking at
            # the VG layer one would think that these related changes would not
            # need locking in the object manager.  We may find that we need
            # to be able to refresh a sequence of changes atomically, esp. when
            # we start supporting nested LVM (LVs that are PVs).

            search = self.lvm_id
            if search_key:
                search = search_key

            cfg.om.remove_object(self)

            # Go out and fetch the latest version of this object, eg.
            # pvs, vgs, lvs
            found = self._ap_search_method(
                [search], self.dbus_object_path())[0]
            for i in found:
                cfg.om.register_object(i)
                changed = get_object_property_diff(self, i)

                if changed:
                    # Use the instance that is registered with dbus API as self
                    # has been removed, calls to it will make no difference
                    # with regards to the dbus API.
                    i.PropertiesChanged(self._ap_interface, changed, [])
                    num_changed += 1
        return num_changed

    @property
    def lvm_id(self):
        """
        Intended to be overridden by classes that inherit
        """
        return str(id(self))

    @property
    def uuid(self):
        """
        Intended to be overridden by classes that inherit
        """
        import uuid
        return uuid.uuid1()


class ObjectManagerLock(object):
    """
    The sole purpose of this class is to allow other code the ability to
    lock the object manager using a `with` statement, eg.

    with cfg.om.locked():
        # Do stuff with object manager

    This will ensure that the lock is always released (assuming this is done
    correctly)
    """

    def __init__(self, recursive_lock):
        self._lock = recursive_lock

    def __enter__(self):
        # Acquire lock
        self._lock.acquire()

    # noinspection PyUnusedLocal
    def __exit__(self, e_type, e_value, e_traceback):
        # Release lock
        self._lock.release()
        self._lock = None


class ObjectManager(AutomatedProperties):
    """
    Implements the org.freedesktop.DBus.ObjectManager interface
    """

    def __init__(self, object_path, interface):
        super(ObjectManager, self).__init__(object_path, interface)
        self._ap_interface = interface
        self._ap_o_path = object_path
        self._objects = {}
        self._id_to_object_path = {}
        self.rlock = threading.RLock()

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.ObjectManager",
                         out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        with self.rlock:
            rc = {}
            try:
                for k, v in self._objects.items():
                    path, props = v[0].emit_data()
                    rc[path] = props
            except Exception:
                traceback.print_exc(file=sys.stdout)
                sys.exit(1)
            return rc

    def locked(self):
        """
        If some external code need to run across a number of different
        calls into ObjectManager while blocking others they can use this method
        to lock others out.
        :return:
        """
        return ObjectManagerLock(self.rlock)

    @dbus.service.signal(dbus_interface="org.freedesktop.DBus.ObjectManager",
                         signature='oa{sa{sv}}')
    def InterfacesAdded(self, object_path, int_name_prop_dict):
        print('SIGNAL: InterfacesAdded(%s, %s)' %
              (str(object_path), str(int_name_prop_dict)))

    @dbus.service.signal(dbus_interface="org.freedesktop.DBus.ObjectManager",
                         signature='oas')
    def InterfacesRemoved(self, object_path, interface_list):
        print('SIGNAL: InterfacesRemoved(%s, %s)' %
              (str(object_path), str(interface_list)))

    def _lookup_add(self, obj, path, lvm_id, uuid):
        """
        Store information about what we added to the caches so that we
        can remove it cleanly
        :param obj:     The dbus object we are storing
        :param path:    The dbus object path
        :param lvm_id:  The user name for the asset
        :param uuid:    The uuid for the asset
        :return:
        """
        # Note: Only called internally, lock implied

        # We could have a temp entry from the forward creation of a path
        self._lookup_remove(path)

        self._objects[path] = (obj, lvm_id, uuid)
        self._id_to_object_path[lvm_id] = path

        if uuid:
            self._id_to_object_path[uuid] = path

    def _lookup_remove(self, obj_path):

        # Note: Only called internally, lock implied
        if obj_path in self._objects:
            (obj, lvm_id, uuid) = self._objects[obj_path]
            del self._id_to_object_path[lvm_id]

            # uuid isn't always available at the moment
            if uuid:
                del self._id_to_object_path[uuid]

            del self._objects[obj_path]

    def object_paths_by_type(self, o_type):
        with self.rlock:
            rc = {}

            for k, v in self._objects.items():
                if isinstance(v[0], o_type):
                    rc[k] = True
            return rc

    def register_object(self, dbus_object, emit_signal=False):
        """
        Given a dbus object add it to the collection
        """
        with self.rlock:
            path, props = dbus_object.emit_data()

            #print 'Registering object path %s for %s' %
            # (path, dbus_object.lvm_id)

            # We want fast access to the object by a number of different ways
            # so we use multiple hashs with different keys
            self._lookup_add(dbus_object, path, dbus_object.lvm_id,
                             dbus_object.uuid)

            if emit_signal:
                self.InterfacesAdded(path, props)

    def remove_object(self, dbus_object, emit_signal=False):
        """
        Given a dbus object, remove it from the collection and remove it
        from the dbus framework as well
        """
        with self.rlock:
            # Store off the object path and the interface first
            path = dbus_object.dbus_object_path()
            interfaces = dbus_object.interface(True)

            #print 'UN-Registering object path %s for %s' % \
            #      (path, dbus_object.lvm_id)

            self._lookup_remove(path)

            # Remove from dbus library
            dbus_object.remove_from_connection(cfg.bus, path)

            # Optionally emit a signal
            if emit_signal:
                self.InterfacesRemoved(path, interfaces)

    def get_by_path(self, path):
        """
        Given a dbus path return the object registered for it
        """
        with self.rlock:
            if path in self._objects:
                return self._objects[path][0]
            return None

    def get_by_uuid_lvm_id(self, uuid, lvm_id):
        with self.rlock:
            return self.get_by_path(
                self.get_object_path_by_lvm_id(uuid, lvm_id, None, False))

    def get_by_lvm_id(self, lvm_id):
        """
        Given an lvm identifier, return the object registered for it
        """
        with self.rlock:
            return self.get_by_path(self._id_to_object_path[lvm_id])

    def get_object_path_by_lvm_id(self, uuid, lvm_id, path_create=None,
                                  gen_new=True):
        """
        For a given lvm asset return the dbus object registered to it
        """
        with self.rlock:
            assert lvm_id       # TODO: Assert that uuid is present later too

            if gen_new:
                assert path_create

            path = None

            if lvm_id in self._id_to_object_path:
                path = self._id_to_object_path[lvm_id]
            else:
                if uuid and uuid in self._id_to_object_path:
                    path = self._id_to_object_path[uuid]
                else:
                    if gen_new:
                        path = path_create()
                        self._lookup_add(None, path, lvm_id, uuid)
            # print 'get_object_path_by_lvm_id(%s, %s, %s: return %s' % \
            #        (uuid, lvm_id, str(gen_new), path)

            return path

    def refresh_all(self):
        with self.rlock:
            for k, v in self._objects.items():
                try:
                    v[0].refresh()
                except Exception:
                    print 'Object path= ', k
                    traceback.print_exc(file=sys.stdout)


def attribute_type_name(name):
    """
    Given the property name, return string of the attribute type
    :param name:
    :return:
    """
    return "_%s_type" % name


_type_map = dict(s=dbus.String,
                 o=dbus.ObjectPath,
                 t=dbus.UInt64,
                 x=dbus.Int64,
                 u=dbus.UInt32,
                 i=dbus.Int32,
                 n=dbus.Int16,
                 q=dbus.UInt16,
                 d=dbus.Double,
                 y=dbus.Byte,
                 b=dbus.Boolean,
                 )


def _pass_through(v):
    """
    If we have something which is not a simple type we return the original
    value un-wrapped.
    :param v:
    :return:
    """
    return v


def _dbus_type(t, value):
    return _type_map.get(t, _pass_through)(value)


##
# This decorator creates a property to be used for dbus introspection
#
def dbus_property(name, dbus_type, default_value=None, writeable=False,
                  doc=None, custom_getter=None, custom_setter=None):
    """
    Creates the get/set properties for the given name.  It assumes that the
    actual attribute is '_' + name and the attribute metadata is stuffed in
    _name_type.

    There is probably a better way todo this.
    :param name:            Name of property
    :param dbus_type:       dbus string type eg. s,t,i,x
    :param default_value:   The default value of the property
    :param writeable:       True == the value can be set
    :param doc:             Python __doc__ for the property
    :return:
    """
    attribute_name = '_' + name

    def getter(self):
        t = getattr(self, attribute_name + '_type')
        return _dbus_type(t, getattr(self, attribute_name))

    def setter(self, value):
        setattr(self, attribute_name, value)

    if custom_getter or custom_setter:
        s = setter
        g = getter

        if custom_getter:
            g = custom_getter
        if custom_setter:
            s = custom_setter

        prop = property(g, s if writeable else None, None, doc)

    else:
        prop = property(getter, setter if writeable else None, None, doc)

    def decorator(cls):
        setattr(cls, attribute_name, default_value)
        setattr(cls, attribute_name + '_type', dbus_type)
        setattr(cls, name, prop)
        return cls

    return decorator


def parse_tags(tags):
    if len(tags):
        if ',' in tags:
            return tags.split(',')
        return [tags]
    return dbus.Array([], signature='s')


# Serializes access to stdout to prevent interleaved output
# @param msg    Message to output to stdout
# @return None
def pprint(msg):
    if cfg.DEBUG:
        cfg.stdout_lock.acquire()
        tid = ctypes.CDLL('libc.so.6').syscall(186)
        print "%d:%d - %s" % (os.getpid(), tid, msg)
        cfg.stdout_lock.release()


# noinspection PyUnusedLocal
def handler(signum, frame):
    cfg.run.value = 0
    pprint('Signal handler called with signal %d' % signum)
    if cfg.loop is not None:
        cfg.loop.quit()


def pv_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return cfg.PV_OBJ_PATH + "/%d" % cfg.pv_id.next()


def vg_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return cfg.VG_OBJ_PATH + "/%d" % cfg.vg_id.next()


def lv_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return cfg.LV_OBJ_PATH + "/%d" % cfg.lv_id.next()


def thin_pool_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return cfg.THIN_POOL_PATH + "/%d" % cfg.thin_id.next()


def job_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return cfg.JOB_OBJ_PATH + "/%d" % cfg.job_id.next()
