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

SEP = '{|}'


def call(command):
    """
    Call an executable and return a tuple of exitcode, stdout, stderr
    """
    #print str(command)

    process = Popen(command, stdout=PIPE, stderr=PIPE, close_fds=True)
    out = process.communicate()

    #print("rc= %d" % process.returncode)
    #print("out= %s\n" % out[0])
    #print("err= %s\n" % out[1])

    return process.returncode, out[0], out[1]


def parse(out):
    rc = []
    for line in out.split('\n'):
        elem = line.split(SEP)
        cleaned_elem = []
        for e in elem:
            e = e.strip()
            cleaned_elem.append(e)

        if len(cleaned_elem) > 1:
            rc.append(cleaned_elem)
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


def pv_remove(device):
    return call(['pvremove', device])


def pv_retrieve(connection):
    rc, out, err = call(['pvs', '--separator', '%s' % SEP, '--nosuffix',
                         '--units', 'b', '-o', 'pv_all'])

    d = []

    if rc == 0:
        d = parse_key_value(out)

    return d

if __name__ == '__main__':
    pv_data = pv_retrieve(None)

    for p in pv_data:
        print str(p)