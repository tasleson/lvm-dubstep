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

import xml.etree.ElementTree as Et
import hashlib
import sys
import inspect
import ctypes
import os

import dbus
import dbus.service
import dbus.mainloop.glib

import cfg


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
def init_class_from_arguments(obj_instance, prefix='_'):
    for k, v in sys._getframe(1).f_locals.items():
        if k != 'self':

            if prefix:
                nt = '_' + k
            else:
                nt = k

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


def dbus_property2(name, dbus_type, doc=None):
    """
    Creates the get/set properties for the given name.  It assumes that the
    actual attribute is '_' + name and the attribute metadata is stuffed in
    _name_type.

    There is probably a better way todo this.
    :param name:            Name of property
    :param dbus_type:       dbus string type eg. s,t,i,x
    :param doc:             Python __doc__ for the property
    :return:
    """
    attribute_name = '_' + name

    def getter(self):
        t = getattr(self, attribute_name + '_type')
        return _dbus_type(t, getattr(self.state, attribute_name[1:]))

    prop = property(getter, None, None, doc)

    def decorator(cls):
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
