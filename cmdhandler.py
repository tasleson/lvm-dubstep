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

from subprocess import Popen, PIPE
import traceback

SEP = '{|}'


def call(command):
    """
    Call an executable and return a tuple of exitcode, stdout, stderr
    """
    print 'STACK:'
    for line in traceback.format_stack():
        print line.strip()

    print 'CMD:', str(command)

    process = Popen(command, stdout=PIPE, stderr=PIPE, close_fds=True)
    out = process.communicate()

    print("EC = %d" % process.returncode)
    print("STDOUT=\n %s\n" % out[0])
    print("STDERR=\n %s\n" % out[1])

    return process.returncode, out[0], out[1]


def parse(out):
    rc = []
    for line in out.split('\n'):
        # This line includes separators, so process them
        if SEP in line:
            elem = line.split(SEP)
            cleaned_elem = []
            for e in elem:
                e = e.strip()
                cleaned_elem.append(e)

            if len(cleaned_elem) > 1:
                rc.append(cleaned_elem)
        else:
            t = line.strip()
            if len(t) > 0:
                rc.append(t)
    return rc


def parse_key_value(out):

    lines = parse(out)
    keys = []
    pvs = []

    # First line will be column headers
    if len(lines) > 0:
        keys = lines[0]

    for i in range(1, len(lines)):
        d = dict(zip(keys, lines[i]))
        pvs.append(d)

    return pvs


def options_to_cli_args(options):
    rc = []
    for k, v in options.items():
        rc.append("--%s" % k)
        rc.append(str(v))
    return rc


def pvs_in_vg(vg_name):
    rc, out, error = call(['vgs', '--noheading',
                            '-o', 'pv_name', vg_name])
    if rc == 0:
        return parse(out)
    return []


def lvs_in_vg(vg_name):
    rc, out, error = call(['vgs', '--noheading',
                            '-o', 'lv_name', vg_name])
    if rc == 0:
        return parse(out)
    return []


def pv_remove(device):
    return call(['pvremove', device])


def vg_remove(vg_name):
    return call(['vgremove', '-f', vg_name])


def vg_lv_create(vg_name, create_options, name, size_bytes):
    cmd = ['lvcreate']
    cmd.extend(options_to_cli_args(create_options))
    cmd.extend(['--size', str(size_bytes) + 'B'])
    cmd.extend(['--name', name, vg_name])
    return call(cmd)


def lv_remove(lv_path):
    return call(['lvremove', '-f', lv_path])


def pv_segments(device):
    r = []

    # pvs --noheading -o pvseg_all

    rc, out, err = call(['pvs', '--separator', '%s' % SEP, '--noheading',
                        '-o', 'pvseg_all'])
    if rc == 0:
        r = parse(out)
    return r


def pv_retrieve(connection, device=None):
    cmd = ['pvs', '--separator', '%s' % SEP, '--nosuffix',
                         '--units', 'b', '-o', 'pv_all']

    if device:
        cmd.extend(device)

    rc, out, err = call(cmd)

    d = []

    if rc == 0:
        d = parse_key_value(out)

    return d


def pv_resize(device, size_bytes):
    cmd = ['pvresize']

    if size_bytes != 0:
        cmd.extend(['--setphysicalvolumesize', str(size_bytes) + 'B'])

    cmd.extend([device])
    return call(cmd)


def pv_create(create_options, devices):
    cmd = ['pvcreate', '-f']
    cmd.extend(options_to_cli_args(create_options))
    cmd.extend(devices)
    return call(cmd)


def vg_create(create_options, pv_devices, name):
    cmd = ['vgcreate']
    cmd.extend(options_to_cli_args(create_options))
    cmd.append(name)
    cmd.extend(pv_devices)
    return call(cmd)


def vg_change(change_options, name):
    cmd = ['vgchange']
    cmd.extend(options_to_cli_args(change_options))
    cmd.append(name)
    return call(cmd)


def vg_retrieve(connection):
    rc, out, err = call(['vgs', '--separator', '%s' % SEP, '--nosuffix',
                         '--units', 'b', '-o', 'vg_all'])

    d = []

    if rc == 0:
        d = parse_key_value(out)

    return d


def lv_retrieve(connection, lv_name):
    cmd = ['lvs', '--separator', '%s' % SEP, '--nosuffix',
         '--units', 'b', '-o',
         'lv_all,seg_start,devices,vg_name,segtype,stripes,tags']

    if lv_name:
        cmd.append(lv_name)

    rc, out, err = call(cmd)

    d = []

    if rc == 0:
        d = parse_key_value(out)

    return d

if __name__ == '__main__':
    pv_data = pv_retrieve(None)

    for p in pv_data:
        print str(p)