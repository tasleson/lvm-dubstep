#!/bin/env python
import xml.etree.ElementTree as Et
import dbus
# noinspection PyUnresolvedReferences
from dbus.mainloop.glib import DBusGMainLoop
import pprint
import collections

pp = pprint.PrettyPrinter(depth=4)


unique_interfaces = {}

INT = 'com.redhat.lvmdbus1'
PATH = '/com/redhat/lvmdbus1'


TYPE_TABLE = {
    'y': 'uint8_t',
    'b': 'Boolean (0 is false, 1 is true)',
    'n': "int16_t",
    'q': "uint16_t",
    'i': "int32_t",
    'u': "uint32_t",
    'x': "int64_t",
    't': "uint64_t",
    'd': "double",
    'h': "Unix file descriptor",
    's': 'String',
    'o': 'Object path',
    'g': 'Signature',
    'v': 'Variant',
    '': 'None'
}


def _get_array(data, i):

    # An array of structures is a() an array with a simple type is just an
    # an array of that one type.  An array of mappings is a{}

    if data[i] != 'a':
        raise Exception("Something wrong here %s" % (data[i]))

    if data[i + 1] == '(':
        r, i = container_type(data, i + 1)
        return "Array of " + r, i
    elif data[i + 1] == '{':
        r, i = _get_mapping(data, i + 1)
        return "Dictionary:" + r, i
    else:
        return "Array of %s " % TYPE_TABLE[data[i + 1]], i + 2


def _get_mapping(data, i):
    if data[i] != '{':
        raise Exception("Something wrong here %s" % (data[i]))

    r, i = container_type(data, i + 1)
    return "{" + r + "}", i


def _get_structure(data, i):
    r, i = container_type(data, i + 1)
    return "Structure (" + r + ")", i


def _append_data(d, msg):
    if d:
        d += ", "
    return d + msg


def container_type(data, i):

    result = ""

    try:
        while True:
            c = data[i]

            if c in '})':
                return result, i + 1
            if c in TYPE_TABLE:
                result = _append_data(result, TYPE_TABLE[c])
                i += 1
            elif c == 'a':
                r, i = _get_array(data, i)
                result = _append_data(result, r)
            elif c == '{':
                r, i = _get_mapping(data, i)
                result = _append_data(result, r)
            elif c == '(':
                r, i = _get_structure(data, i)
                result = _append_data(result, r)
            else:
                raise Exception("Unexpected type character %s" % (c))
    except IndexError:
        pass

    return result, i


def type_to_human(t):
    if t in TYPE_TABLE:
        return TYPE_TABLE[t]
    else:
        return container_type(t, 0)[0]


def ouput_interfaces(interfaces):

    for interface_name, md in sorted(interfaces.items()):
        print('\n## Interface %s ##' % (interface_name))
        print('\n#### Methods ####')
        for k, v in sorted(md['methods'].items()):
            print('* %s' % k)

            if len(list(v['args'].keys())) == 0:
                print('  * Arguments (None)')
            else:
                # These need to be in the order supplied
                print('  * Arguments')
                for arg_name, arg_type in list(v['args'].items()):
                    print('      * %s (%s)' %
                          (arg_name, type_to_human(arg_type)))
            print('  * Returns')
            print('      * %s' % (type_to_human(v['return_val'])))
        print('\n#### Properties ####')
        for p, t in sorted(md['properties'].items()):
            print('* %s (%s)' % (p, type_to_human(t['prop_type'])))


def get_methods(et_methods):
    methods = collections.OrderedDict()

    for m in sorted(et_methods.iter('method')):
        method_name = m.attrib['name']
        arguments_in = collections.OrderedDict()
        return_val = ""

        for args in m:
            direction = args.attrib['direction']
            arg_type = args.attrib['type']

            if direction == 'in':
                name = str(args.attrib['name'])
                arguments_in[name] = str(arg_type)
            else:
                return_val = arg_type

        methods[method_name] = dict(args=arguments_in, return_val=return_val)

    return methods


def get_properties(et_props):
    props = collections.OrderedDict()

    for p in sorted(et_props.iter('property')):
        #print p.tag, p.attrib
        name = p.attrib['name']
        prop_type = p.attrib['type']
        access = p.attrib['access']
        props[name] = dict(prop_type=prop_type, access=access)

    return props


def get_introspect_data(bus, object_p, interface):
    obj = bus.get_object(INT, object_p)
    intf = dbus.Interface(obj, "org.freedesktop.DBus.Introspectable")

    intf_data = intf.Introspect()

    tree = Et.fromstring(intf_data)
    interfaces = collections.OrderedDict()
    for i in sorted(tree.iter('interface')):

        if i.attrib['name'] == interface:
            interfaces[interface] = dict(methods=None, properties=None)
            interfaces[interface]['methods'] = get_methods(i)
            interfaces[interface]['properties'] = get_properties(i)

    ouput_interfaces(interfaces)


def _get_doc():

    bus = dbus.SystemBus(mainloop=DBusGMainLoop())
    manager = dbus.Interface(bus.get_object(INT, PATH),
                             "org.freedesktop.DBus.ObjectManager")

    objects = manager.GetManagedObjects()

    for object_path, val in list(objects.items()):
        keys = [k for k in list(val.keys()) if k[0:len(INT)] == INT]

        for k in keys:
            unique_interfaces[str(k)] = dict(object_path=object_path)

    for k, v in sorted(unique_interfaces.items()):
        get_introspect_data(bus, v['object_path'], k)

if __name__ == "__main__":
    _get_doc()
