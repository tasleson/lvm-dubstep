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

import dbus
import xml.etree.ElementTree as Et
import sys


def is_numeric(s):
    try:
        long(s)
        return True
    except ValueError:
        return False


def n(v):
    if not v:
        return 0L
    if v.endswith('B'):
        return long(v[:-1])
    return long(v)


# noinspection PyProtectedMember
def init_class_from_arguments(obj_instance):
    for k, v in sys._getframe(1).f_locals.items():
        if k != 'self':
            nt = '_' + k
            # print 'Init class %s = %s' % (nt, str(v))
            setattr(obj_instance, nt, v)


def get_properties(f):
    """
    Walks through an object instance and determines which attributes are
    properties and if they were created to be used for dbus.
    :param f:
    :return:    A tuple:
                0 = An array of dicts with the keys being: p_t, p_name,
                p_access(type, name, access)
                1 = Hash of property names and current value
    """
    result = []
    h_rc = {}

    h = vars(f.__class__)
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


# noinspection PyUnresolvedReferences
class AutomatedProperties(dbus.service.Object):
    def __init__(self, conn, object_path, interface):
        #dbus.service.Object.__init__(self, conn, object_path)
        super(AutomatedProperties, self).__init__(conn, object_path)
        self._ap_c = conn
        self._ap_interface = interface
        self._ap_o_path = object_path

    def emit_data(self):
        return self._ap_o_path, self.GetAll(self._ap_interface)

    def interface(self):
        return self._ap_interface

    # Properties
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
        if interface_name == self._ap_interface:
            # Using introspection, lets build this dynamically
            props = get_properties(self)[0]

            rc = {}
            for p in props:
                rc[p['p_name']] = getattr(self, p['p_name'])
            return rc

        raise dbus.exceptions.DBusException(
            self._ap_interface,
            'The object %s does not implement the %s interface'
            % (self.__class__, interface_name))

    @dbus.service.method(dbus_interface=dbus.PROPERTIES_IFACE,
                         in_signature='ssv')
    def Set(self, interface_name, property_name, new_value):
        pass

    # As dbus-python does not support introspection for properties we will
    # get the autogenerated xml and then add our wanted properties to it.
    @dbus.service.method(dbus_interface=dbus.INTROSPECTABLE_IFACE,
                         out_signature='s')
    def Introspect(self):
        r = super(AutomatedProperties, self).Introspect(
            self._ap_o_path, self._ap_c)

        # Look at the properties in the class
        return add_properties(r, self._ap_interface, get_properties(self)[0])

    @dbus.service.signal(dbus_interface=dbus.PROPERTIES_IFACE,
                         signature='sa{sv}as')
    def PropertiesChanged(self, interface_name, changed_properties,
                          invalidated_properties):
        print('SIGNAL: PropertiesChanged(%s, %s, %s)' %
              (str(interface_name), str(changed_properties),
               str(invalidated_properties)))

    def refresh_object(self, search_method, search_value):
        """
        Not sure if there is a better way to do this, instead of
        resorting to removing the existing object and inserting a new
        one.
        """

        self.remove_from_connection(self._c, self._object_path)
        self._object_manager.remove_object(self)

        found = search_method(self._ap_c, self._object_manager,
                                [search_value])
        for i in found:
            self._object_manager.register_object(i)
            changed = get_object_property_diff(self, i)

            if changed:
                self.PropertiesChanged(self.interface(), changed, None)

    def lvm_id(self):
        return None


# noinspection PyUnresolvedReferences
class ObjectManager(AutomatedProperties):

    def __init__(self, conn, object_path, interface):
        super(ObjectManager, self).__init__(conn, object_path, interface)
        self._ap_c = conn
        self._ap_interface = interface
        self._ap_o_path = object_path
        self._objects = {}

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.ObjectManager",
                         out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        rc = {}
        for k, v in self._objects.items():
            path, props = v.emit_data()
            i = {v.interface(): props}
            rc[path] = i
        return rc

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

    def register_object(self, dbus_object, emit_signal=False):
        path, props = dbus_object.emit_data()
        self._objects[path] = dbus_object

        if emit_signal:
            i = {dbus_object.interface(): props}
            self.InterfacesAdded(path, i)

    def remove_object(self, dbus_object, emit_signal=False):
        path, props = dbus_object.emit_data()

        del self._objects[path]
        if emit_signal:
            self.InterfacesRemoved(path, dbus_object.interface())

    def get_object(self, path):
        if path in self._objects:
            return self._objects[path]
        return None


def attribute_type_name(name):
    """
    Given the property name, return string of the attribute type
    :param name:
    :return:
    """
    return "_%s_type" % name


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
        # We could wrap the value up in specific type...
        return getattr(self, attribute_name)

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
