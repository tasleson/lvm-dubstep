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
# Copyright 2015, Vratislav Podzimek <vpodzime@redhat.com>

import subprocess
import shlex
from fcntl import fcntl, F_GETFL, F_SETFL
from os import O_NONBLOCK
from . import cfg

SHELL_PROMPT = "lvm> "


def _quote_arg(arg):
    if len(shlex.split(arg)) > 1:
        return '"%s"' % arg
    else:
        return arg


class LVMShellProxy(object):
    def __init__(self):
        # run the lvm shell
        self.lvm_shell = subprocess.Popen(
            [cfg.LVM_CMD], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True)
        flags = fcntl(self.lvm_shell.stdout, F_GETFL)
        fcntl(self.lvm_shell.stdout, F_SETFL, flags | O_NONBLOCK)
        flags = fcntl(self.lvm_shell.stderr, F_GETFL)
        fcntl(self.lvm_shell.stderr, F_SETFL, flags | O_NONBLOCK)

        # wait for the first prompt
        stdout = ""
        while not stdout.endswith(SHELL_PROMPT):
            try:
                stdout += self.lvm_shell.stdout.read()
            except IOError:
                # nothing written yet
                pass

    def call_lvm(self, argv, debug=False):
        # create the command string
        cmd = " ".join(_quote_arg(arg) for arg in argv)
        cmd += "\n"

        # run the command by writing it to the shell's STDIN
        self.lvm_shell.stdin.write(cmd)

        # read and discard the first line (the shell echoes the command string,
        # no idea why)
        line = None
        while line is None:
            try:
                line = self.lvm_shell.stdout.readline()
            except IOError:
                # nothing written yet
                pass

        # read everything from the STDOUT to the next prompt
        stdout = ""
        while not stdout.endswith(SHELL_PROMPT):
            try:
                stdout += self.lvm_shell.stdout.read()
            except IOError:
                # nothing written yet
                pass

        # strip the prompt from the STDOUT
        strip_idx = -1 * len(SHELL_PROMPT)
        stdout = stdout[:strip_idx]

        # read everything from STDERR if there's something (we waited for the
        # prompt on STDOUT so there should be all or nothing at this point on
        # STDERR)
        stderr = None
        try:
            stderr = self.lvm_shell.stderr.read()
        except IOError:
            # nothing on STDERR
            pass

        # if there was something on STDERR, there was some error
        if stderr:
            rc = 1
        else:
            rc = 0

        if debug or rc != 0:
            print(('CMD: %s' % cmd))
            print(("EC = %d" % rc))
            print(("STDOUT=\n %s\n" % stdout))
            print(("STDERR=\n %s\n" % stderr))

        return (rc, stdout, stderr)

    def __del__(self):
        self.lvm_shell.terminate()

if __name__ == "__main__":
    shell = LVMShellProxy()
    in_line = "start"
    try:
        while in_line:
            in_line = input("lvm> ")
            if in_line:
                ret, out, err, = shell.call_lvm(in_line.split())
                print(("RET: %d" % ret))
                print(("OUT:\n%s" % out))
                print(("ERR:\n%s" % err))
    except Exception:
        pass
    finally:
        print()
