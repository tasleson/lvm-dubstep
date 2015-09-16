#!/usr/bin/env python2

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
import string
import socket


_IDENT_CH = string.ascii_letters + string.digits + '_.-'
_WHITESPACE_CH = ' \t\n\r'
_NUMBER_CH = string.digits + '.'


def _ws(data, i):
    while data[i] in _WHITESPACE_CH:
        i += 1
    return i


def _comment(data, i):
    if data[i] != '#':
        raise Exception(
            """Comment expecting'#' not %s, pos= %d, data= %s""" %
            (data[i], i, data[i:i + 100]))

    while data[i] != "\n":
        i += 1
    return i + 1        # Chomp new '\n'


def _get_identifier(data, i):
    st = i
    while data[i] in _IDENT_CH:
        i += 1
    return data[st:i], i


def _get_number(data, i):
    rc = None
    st = i

    while data[i] in _NUMBER_CH:
        i += 1

    raw = data[st:i]

    if '.' in raw:
        rc = float(raw)
    else:
        rc = long(raw)

    return rc, i


def _get_string(data, i):

    if data[i] != '"':
        raise Exception(
            """String expecting '"' not %s, pos= %d, data= %s""" %
            (data[i], i, data[i:i + 100]))
    i += 1
    st = i

    while data[i] != '"':
        i += 1
    return data[st:i], i + 1            # Chomp the ending '"'


def _get_array(data, i):
    rc = []

    if data[i] != '[':
        raise Exception("Array expecting '[' not %s, pos= %d, data= %s" %
                        (data[i], i, data[i:i + 100]))

    i += 1

    while True:
        ch = data[i]

        if ch in _WHITESPACE_CH:
            i = _ws(data, i)
        elif ch == '#':
            i = _comment(data, i)
        else:
            # We should only be processing, numbers or strings
            if ch == '"':
                value, i = _get_string(data, i)
                rc.append(value)
            elif ch in _NUMBER_CH:
                value, i = _get_number(data, i)
                rc.append(value)
            elif ch == ',':
                i += 1
            elif ch == ']':
                i += 1
                break
            else:
                raise Exception("Array, unexpected character %s, pos= %d, "
                                "data= %s" % (ch, i, data[i:i + 100]))
    return rc, i


def _get_object(data, i, nested=False):

    rc = {}

    identifier = ''
    state = "U"

    if data is None or len(data) == 0:
        return {}, 0

    try:
        while True:
            ch = data[i:i + 1]

            if ch in _WHITESPACE_CH:
                i = _ws(data, i)
            elif ch == '#':
                i = _comment(data, i)
            else:
                if state == "U":
                    if ch in _IDENT_CH:
                        (identifier, i) = _get_identifier(data, i)
                        state = "A"
                    elif nested and ch == '}':
                        i += 1
                        break
                    else:
                        raise Exception(
                            "Unexpected character %s, pos= %d, "
                            "state= %s, data= %s" %
                            (ch, i, state, data[i:i + 100]))
                elif state == "A":
                    # Look for assignment operator or {
                    if ch == '=':
                        # Simple data type
                        state = 'S'
                        i += 1
                    elif ch == '{':
                        # Section
                        i += 1
                        rc[identifier], i = \
                            _get_object(data, i, True)
                        state = 'U'
                    else:
                        raise Exception(
                            "Unexpected character %s, pos= %d, "
                            "state= %s, data= %s" %
                            (ch, i, state, data[i:i + 100]))

                elif state == "S":
                    # We are dealing with a number, array or string
                    if ch == '[':
                        rc[identifier], i = _get_array(data, i)
                        state = 'U'
                    elif ch == '"':
                        rc[identifier], i = _get_string(data, i)
                        state = 'U'
                    elif ch in string.digits:
                        # Does the format support negative numbers, doesn't
                        # appear too based on `man 5 lvm.conf`
                        rc[identifier], i = _get_number(data, i)
                        state = 'U'
                    else:
                        raise Exception(
                            "Unexpected character %s, pos= %d, "
                            "state= %s, data= %s" %
                            (ch, i, state, data[i:i + 100]))
                else:
                    raise Exception("Unexpected state %s, pos= %d, "
                                        "state= %s, data= %s" %
                                        (ch, i, state, data[i:i + 100]))

    except IndexError:
        if state != "U":
            raise Exception("Malformed input, expecting more...")
    return rc, i


class Lvmetad(object):

    SOCKET = '/run/lvm/lvmetad.socket'
    END = '''\n##\n'''

    def __init__(self):
        self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.s.connect(Lvmetad.SOCKET)

    def close(self):
        self.s.close()
        self.s = None

    def __enter__(self):
        if not self.s:
            # Get a socket to use
            self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.s.connect(Lvmetad.SOCKET)
        return self

    def __exit__(self, *ignore):
        self.close()

    @staticmethod
    def parse(data):
        return _get_object(data, 0)[0]

    def _request(self, cmd, args=None):
        req = '''request = "%s"\n''' % cmd

        if args:
            for k, v in args.items():
                req += '''%s =\"%s"\n''' % (k, v)

        req += '''token = "filter:0"\n'''
        self.s.sendall(req)
        self.s.sendall(self.END)

        data = ''
        while self.END not in data:
            data += self.s.recv(1024)

        with open('/tmp/lvmetad', 'w') as debug:
            debug.write(data)
        return data

    def all(self):
        return self.parse(self._request('dump'))


if __name__ == '__main__':
    with Lvmetad() as meta:
        everything = meta.all()
        #print str(everything)
