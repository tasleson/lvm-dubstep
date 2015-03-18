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
import sys

SEP = '{|}'


# Default cmd
# Place default arguments for every command here.
def _dc(cmd, args):
    c = [cmd, '--noheading', '--separator', '%s' % SEP, '--nosuffix',
         '--unbuffered', '--units', 'b']
    c.extend(args)
    return c


def call(command, debug=True):
    """
    Call an executable and return a tuple of exitcode, stdout, stderr
    """
    #print 'STACK:'
    #for line in traceback.format_stack():
    #    print line.strip()

    if debug:
        print 'CMD:', ' '.join(command)

    process = Popen(command, stdout=PIPE, stderr=PIPE, close_fds=True)
    out = process.communicate()

    if debug:
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


def parse_column_names(out, column_names):
    lines = parse(out)
    rc = []

    for i in range(0, len(lines)):
        d = dict(zip(column_names, lines[i]))
        rc.append(d)

    return rc


def options_to_cli_args(options):
    rc = []
    for k, v in options.items():
        rc.append("--%s" % k)
        rc.append(str(v))
    return rc


def pvs_in_vg(vg_name):
    rc, out, error = call(_dc('vgs', ['-o', 'pv_name', vg_name]))
    if rc == 0:
        return parse(out)
    return []


def lvs_in_vg(vg_name):
    rc, out, error = call(_dc('vgs', ['lv_name', vg_name]))
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


def lv_lv_create(lv_full_name, create_options, name, size_bytes):
    cmd = ['lvcreate']
    cmd.extend(options_to_cli_args(create_options))
    cmd.extend(['--virtualsize', str(size_bytes) + 'B', '-T'])
    cmd.extend(['--name', name, lv_full_name])
    return call(cmd)


def pv_segments(device):
    r = []
    rc, out, err = call(_dc('pvs', ['-o', 'pvseg_all', device]))
    if rc == 0:
        r = parse(out)
    return r


def pv_retrieve(connection, device=None):
    columns = ['pv_name', 'pv_uuid', 'pv_fmt', 'pv_size', 'pv_free',
               'pv_used', 'dev_size', 'pv_mda_size', 'pv_mda_free',
               'pv_ba_start', 'pv_ba_size', 'pe_start', 'pv_pe_count',
               'pv_pe_alloc_count', 'pv_attr', 'pv_tags', 'vg_name']

    cmd = _dc('pvs', ['-o', ','.join(columns)])

    if device:
        cmd.extend(device)

    rc, out, err = call(cmd)

    d = []

    if rc == 0:
        d = parse_column_names(out, columns)

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


def pv_move_lv(move_options, lv_full_name,
                pv_source, pv_source_range, pv_dest, pv_dest_range):
    cmd = ['pvmove', '-b']
    cmd.extend(options_to_cli_args(move_options))

    cmd.extend(['-n', lv_full_name])

    if pv_source_range[1] != 0:
        cmd.append("%s-%d:%d" %
                   (pv_source, pv_source_range[0], pv_source_range[1]))
    else:
        cmd.append(pv_source)

    if pv_dest:
        if pv_dest_range[1] != 0:
            cmd.append("%s-%d:%d" %
                       (pv_dest, pv_dest_range[0], pv_dest_range[1]))
        else:
            cmd.append(pv_dest)

    return call(cmd)


def _pv_move_find_lv(lookup, device_name, vg_name):
    for l in lookup:
        if device_name in l['devices'] and l['vg_name'] == vg_name:
            return l['lv_name']
    return None


def pv_move_status():
    lv_in_motion = {}

    columns = ['pv_name', 'lv_uuid', 'vg_name', 'lv_name', 'devices',
               'copy_percent']

    cmd = _dc('pvs', ['-o' + ','.join(columns), '-S', 'copy_percent>=0'])

    lookup_columns = ['lv_name', 'vg_name', 'devices']

    lookup = _dc('lvs', ['-o' + ','.join(lookup_columns),
                         '-S', 'devices=~"pvmove[0-9]+"'])

    rc, out, err = call(cmd, False)
    if rc == 0:
        lines = parse_column_names(out, columns)
        if len(lines) > 0:
            rc, lookup_out, lookup_err = call(lookup, False)

            if rc == 0:
                lookup = parse_column_names(lookup_out, lookup_columns)

                for l in lines:
                    if l['lv_name'][0] == '[':
                        l['lv_name'] = l['lv_name'][1:-1]

                    # Parse the devices
                    src, dest = l['devices'].split(',')
                    src = src.split('(')[0]
                    dest = dest.split('(')[0]

                    if l['pv_name'] != src:
                        continue

                    lv_being_moved = _pv_move_find_lv(lookup, l['lv_name'],
                                                      l['vg_name'])

                    lv_full_name = "%s/%s" % (l['vg_name'], lv_being_moved)

                    if lv_full_name not in lv_in_motion:
                        lv_in_motion[lv_full_name] = \
                            dict(src_dev=src,
                                 dest_dev=dest,
                                 percent=int(float(l['copy_percent'])))

    return lv_in_motion


def pv_allocatable(device, yes):
    yn = 'n'

    if yes:
        yn = 'y'

    cmd = ['pvchange', '-x', yn, device]
    return call(cmd)


def pv_contained_lv(device):
    data = []
    tmp = {}
    cmd = _dc('lvs', ['-o', 'lv_name,seg_pe_ranges',
                      '-S', 'seg_pe_ranges=~"%s.*"' % (device)])

    rc, out, err = call(cmd)
    if rc == 0:
        d = parse(out)
        for l in d:
            lv = l[0]
            pe = l[1]
            seg = pe.split(':')[1]
            r1, r2 = seg.split('-')

            if lv in tmp:
                tmp[lv].append((r1, r2))
            else:
                tmp[lv] = [((r1, r2))]

        for k, v in tmp.items():
            data.append((k, v))

    return data


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


def vg_reduce(vg_name, missing, pv_devices):
    cmd = ['vgreduce']
    if len(pv_devices) == 0:
        cmd.append('--all')
    if missing:
        cmd.append('--removemissing')

    cmd.append(vg_name)

    cmd.extend(pv_devices)
    return call(cmd)


def vg_extend(vg_name, extend_devices):
    cmd = ['vgextend', vg_name]
    cmd.extend(extend_devices)
    return call(cmd)


def vg_retrieve(connection, vg_specific):
    columns = ['vg_name', 'vg_uuid', 'vg_fmt', 'vg_size', 'vg_free',
               'vg_sysid', 'vg_extent_size', 'vg_extent_count',
               'vg_free_count', 'vg_profile', 'max_lv', 'max_pv',
               'pv_count', 'lv_count', 'snap_count', 'vg_seqno',
               'vg_mda_count', 'vg_mda_free', 'vg_mda_size',
               'vg_mda_used_count', 'vg_attr', 'vg_tags']

    cmd = _dc('vgs', ['-o', ','.join(columns)])

    if vg_specific:
        cmd.extend(vg_specific)

    d = []
    rc, out, err = call(cmd)
    if rc == 0:
        d = parse_column_names(out, columns)

    return d


def lv_retrieve(connection, lv_name):
    columns = ['lv_uuid', 'lv_name', 'lv_path', 'lv_size',
                'vg_name', 'pool_lv',
                'origin', 'data_percent',
               'lv_attr', 'lv_tags']

    cmd = _dc('lvs', ['-o', ','.join(columns)])

    if lv_name:
        cmd.extend(lv_name)

    rc, out, err = call(cmd)

    d = []

    if rc == 0:
        d = parse_column_names(out, columns)

    return d


def _pv_device(data, device):
    device, seg = device.split(':')
    r1, r2 = seg.split('-')

    if device in data:
        data[device].append((r1, r2))
    else:
        data[device] = [((r1, r2))]


def lv_pv_devices(lv_name):
    data = []
    tmp = {}

    cmd = _dc('pvs', ['-o', 'seg_pe_ranges', '-S',
                      'lv_full_name=~"%s.+"' % lv_name])

    rc, out, err = call(cmd, True)

    try:
        if rc == 0:
            d = parse(out)
            for l in d:
                # We have a striped result set where all lines are repeats
                # so handle this line and break out.
                # No idea why this is the odd one!
                if ' ' in l:
                    devices = l.split(' ')
                    for d in devices:
                        _pv_device(tmp, d)
                    break
                else:
                    _pv_device(tmp, l)

            for k, v in tmp.items():
                data.append((k, v))

    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        pass

    return data

if __name__ == '__main__':
    pv_data = pv_retrieve(None)

    for p in pv_data:
        print str(p)