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

from . import cfg


def md5(t):
    # noinspection PyUnresolvedReferences
    h = hashlib.md5()
    h.update(t)
    return h.hexdigest()


def is_numeric(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def rtype(dbus_type):
    """
    Decorator making sure that the decorated function returns a value of
    specified type.
    :param dbus_type: The specific dbus type to return value as
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
        return 0
    if v.endswith('B'):
        return int(v[:-1])
    return int(float(v))


@rtype(dbus.UInt32)
def n32(v):
    if not v:
        return 0
    if v.endswith('B'):
        return int(v[:-1])
    return int(float(v))


# noinspection PyProtectedMember
def init_class_from_arguments(obj_instance, prefix='_'):
    for k, v in list(sys._getframe(1).f_locals.items()):
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


def get_properties(f):
    """
    Walks through an object instance or it's parent class(es) and determines
    which attributes are properties and if they were created to be used for
    dbus.
    :param f:   Object to inspect
    :return:    A dictionary of tuples with each tuple being:
                0 = An array of dicts with the keys being: p_t, p_name,
                p_access(type, name, access)
                1 = Hash of property names and current value
    """
    interfaces = dict()

    for c in inspect.getmro(f.__class__):

        h = vars(c)
        for p, value in h.items():
            if isinstance(value, property):
                # We found a property, see if it has a metadata type
                key = attribute_type_name(p)
                if key in h:
                    interface = h[key][1]

                    if interface not in interfaces:
                        interfaces[interface] = ([], {})

                    access = ''
                    if getattr(f.__class__, p).fget:
                        access += 'read'
                    if getattr(f.__class__, p).fset:
                        access += 'write'

                    interfaces[interface][0].append(
                        dict(p_t=getattr(f, key)[0],
                             p_name=p,
                             p_access=access))

                    interfaces[interface][1][p] = getattr(f, p)

    return interfaces


def get_object_property_diff(o_prop, n_prop):
    """
    Walk through each object properties and report what has changed and with
    the new values
    :param o_prop:   Old keys/values
    :param n_prop:   New keys/values
    :return: hash of properties that have changed and their new value
    """
    rc = {}

    for intf_k, intf_v in o_prop.items():
        for k, v in list(intf_v[1].items()):
            #print('Comparing %s:%s to %s:%s' %
            #      (k, o_prop[intf_k][1][k], k, str(n_prop[intf_k][1][k])))
            if o_prop[intf_k][1][k] != n_prop[intf_k][1][k]:
                new_value = n_prop[intf_k][1][k]

                if intf_k not in rc:
                    rc[intf_k] = dict()

                rc[intf_k][k] = new_value
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

    if props:

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
    return "_%s_meta" % name


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


def dbus_property(interface_name, name, dbus_type, doc=None):
    """
    Creates the get/set properties for the given name.  It assumes that the
    actual attribute is '_' + name and the attribute metadata is stuffed in
    _name_type.

    There is probably a better way todo this.
    :param interface_name:  Dbus interface this property is associated with
    :param name:            Name of property
    :param dbus_type:       dbus string type eg. s,t,i,x
    :param doc:             Python __doc__ for the property
    :return:
    """
    attribute_name = '_' + name

    def getter(self):
        t = getattr(self, attribute_name + '_meta')[0]
        return _dbus_type(t, getattr(self.state, attribute_name[1:]))

    prop = property(getter, None, None, doc)

    def decorator(cls):
        setattr(cls, attribute_name + '_meta', (dbus_type, interface_name))
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
def pprint(msg, *attributes):
    if cfg.DEBUG:
        cfg.stdout_lock.acquire()
        tid = ctypes.CDLL('libc.so.6').syscall(186)

        msg = "%d:%d - %s" % (os.getpid(), tid, msg)

        if attributes:
            print(color(msg, *attributes))
        else:
            print(msg)

        cfg.stdout_lock.release()
        sys.stdout.flush()


# noinspection PyUnusedLocal
def handler(signum, frame):
    cfg.run.value = 0
    pprint('Signal handler called with signal %d' % signum)
    if cfg.loop is not None:
        cfg.loop.quit()


def pv_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return cfg.PV_OBJ_PATH + "/%d" % next(cfg.pv_id)


def vg_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return cfg.VG_OBJ_PATH + "/%d" % next(cfg.vg_id)


def lv_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return cfg.LV_OBJ_PATH + "/%d" % next(cfg.lv_id)


def thin_pool_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return cfg.THIN_POOL_PATH + "/%d" % next(cfg.thin_id)


def hidden_lv_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return cfg.HIDDEN_LV_PATH + "/%d" % next(cfg.hidden_lv)


def job_obj_path_generate(object_path=None):
    if object_path:
        return object_path
    return cfg.JOB_OBJ_PATH + "/%d" % next(cfg.job_id)


def color(text, *user_styles):

    styles = {
        # styles
        'reset': '\033[0m',
        'bold': '\033[01m',
        'disabled': '\033[02m',
        'underline': '\033[04m',
        'reverse': '\033[07m',
        'strike_through': '\033[09m',
        'invisible': '\033[08m',
        # text colors
        'fg_black': '\033[30m',
        'fg_red': '\033[31m',
        'fg_green': '\033[32m',
        'fg_orange': '\033[33m',
        'fg_blue': '\033[34m',
        'fg_purple': '\033[35m',
        'fg_cyan': '\033[36m',
        'fg_light_grey': '\033[37m',
        'fg_dark_grey': '\033[90m',
        'fg_light_red': '\033[91m',
        'fg_light_green': '\033[92m',
        'fg_yellow': '\033[93m',
        'fg_light_blue': '\033[94m',
        'fg_pink': '\033[95m',
        'fg_light_cyan': '\033[96m',
        # background colors
        'bg_black': '\033[40m',
        'bg_red': '\033[41m',
        'bg_green': '\033[42m',
        'bg_orange': '\033[43m',
        'bg_blue': '\033[44m',
        'bg_purple': '\033[45m',
        'bg_cyan': '\033[46m',
        'bg_light_grey': '\033[47m'
    }

    color_text = ''
    for style in user_styles:
        try:
            color_text += styles[style]
        except KeyError:
            return 'def color: parameter {} does not exist'.format(style)
    color_text += text
    return '\033[0m{0}\033[0m'.format(color_text)


def pv_range_append(cmd, device, start, end):

    if (start, end) == (0, 0):
        cmd.append(device)
    else:
        if start != 0 and end == 0:
            cmd.append("%s:%d-" % (device, start))
        else:
            cmd.append("%s:%d-%d" %
                       (device, start, end))


def pv_dest_ranges(cmd, pv_dest_range_list):
    if len(pv_dest_range_list):
        for i in pv_dest_range_list:
            pv_range_append(cmd, *i)
