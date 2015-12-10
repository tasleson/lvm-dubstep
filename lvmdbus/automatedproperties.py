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
from . import cfg
from .utils import get_properties, add_properties, get_object_property_diff
from .state import State


# noinspection PyPep8Naming
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
        self.state = None

    def dbus_object_path(self):
        return self._ap_o_path

    def emit_data(self):
        props = {}

        for i in self.interface():
            props[i] = self.GetAll(i)

        return self._ap_o_path, props

    # noinspection PyUnusedLocal
    def interface(self, all_interfaces=False):
        return [self._ap_interface]

    # Properties
    # noinspection PyUnusedLocal
    @dbus.service.method(dbus_interface=dbus.PROPERTIES_IFACE,
                         in_signature='ss', out_signature='v')
    def Get(self, interface_name, property_name):
        value = getattr(self, property_name)
        # Note: If we get an exception in this handler we won't know about it,
        # only the side effect of no returned value!
        print('Get (%s), type (%s), value(%s)' %
              (property_name, str(type(value)), str(value)))
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
        print(('SIGNAL: PropertiesChanged(%s, %s, %s, %s)' %
              (str(self._ap_o_path), str(interface_name),
               str(changed_properties), str(invalidated_properties))))

    def refresh(self, search_key=None, object_state=None):
        """
        Take the values (properties) of an object and update them with what
        lvm currently has.  You can either fetch the new ones or supply the
        new state to be updated with
        :param search_key: The value to use to search for
        :param object_state: Use this as the new object state
        """
        num_changed = 0

        # If we can't do a lookup, bail now, this happens if we blindly walk
        # through all dbus objects as some don't have a search method, like
        # 'Manager' object.
        if not self._ap_search_method:
            return

        search = self.lvm_id
        if search_key:
            search = search_key

        # Either we have the new object state or we need to go fetch it
        if object_state:
            new_state = object_state
        else:
            new_state = self._ap_search_method([search])[0]
            assert isinstance(new_state, State)

        assert new_state

        # When we refresh an object the object identifiers might have changed
        # because LVM allows the user to change them (name & uuid), thus if
        # they have changed we need to update the object manager so that
        # look-ups will happen correctly
        old_id = self.state.identifiers()
        new_id = new_state.identifiers()
        if old_id[0] != new_id[0] or old_id[1] != new_id[1]:
            cfg.om.lookup_update(self)

        # Grab the properties values, then replace the state of the object
        # and retrieve the new values
        # TODO: We need to add locking to prevent concurrent access to the
        # properties so that a client is not accessing while we are
        # replacing.
        o_prop = get_properties(self)[1]
        self.state = new_state
        n_prop = get_properties(self)[1]

        changed = get_object_property_diff(o_prop, n_prop)

        if changed:
            self.PropertiesChanged(self._ap_interface, changed, [])
            num_changed += 1
        return num_changed
