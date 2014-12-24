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


def get_properties(f):
    """
    Walks through an object instance and determines which attributes are
    properties and if they were created to be used for dbus.
    :param f:
    :return:    An array of dicts with the keys being: p_t, p_name, p_access
                (type, name, access)
    """
    result = []
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
    return result


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
        print c.attrib['name']
        if c.attrib['name'] == interface:
            for p in props:
                temp = '<property type="%s" name="%s" access="%s"/>\n' % \
                       (p['p_t'], p['p_name'], p['p_access'])
                c.append(Et.fromstring(temp))

            return Et.tostring(root, encoding='utf8')
    return xml


class AutomatedProperties(dbus.service.Object):
    def __init__(self, conn, object_path, interface):
        dbus.service.Object.__init__(self, conn, object_path)
        self.interface = interface

    # Properties
    @dbus.service.method(dbus_interface=dbus.PROPERTIES_IFACE,
                         in_signature='ss', out_signature='v')
    def Get(self, interface_name, property_name):
        return self.GetAll(interface_name)[property_name]

    @dbus.service.method(dbus_interface=dbus.PROPERTIES_IFACE,
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface_name):
        if interface_name == self.interface:
            # Using introspection, lets build this dynamically
            props = get_properties(self)

            rc = {}
            for p in props:
                rc[p['p_name']] = getattr(self, p['p_name'])
            return rc

        raise dbus.exceptions.DBusException(
            self.interface,
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
        r = super(AutomatedProperties, self).Introspect(self.o_path, self.c)

        # Look at the properties in the class
        return add_properties(r, self.interface, get_properties(self))


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
                  doc=None):
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

    prop = property(getter, setter if writeable else None, None, doc)

    def decorator(cls):
        setattr(cls, attribute_name, default_value)
        setattr(cls, attribute_name + '_type', dbus_type)
        setattr(cls, name, prop)
        return cls

    return decorator
