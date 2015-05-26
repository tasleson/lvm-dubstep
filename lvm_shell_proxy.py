#!/usr/bin/python

import subprocess
import shlex
from fcntl import fcntl, F_GETFL, F_SETFL
from os import O_NONBLOCK

SHELL = "lvm"
SHELL_PROMPT = "lvm> "

def _quote_arg(arg):
    if len(shlex.split(arg)) > 1:
        return '"%s"' % arg
    else:
        return arg

class LVMShellProxy(object):
    def __init__(self):
        # run the lvm shell
        self.lvm_shell = subprocess.Popen([SHELL], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
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
            ret = 1
        else:
            ret = 0

        if debug or ret != 0:
            print('CMD: %s' % cmd)
            print("EC = %d" % ret)
            print("STDOUT=\n %s\n" % stdout)
            print("STDERR=\n %s\n" % stderr)

        return (ret, stdout, stderr)

    def __del__(self):
        self.lvm_shell.terminate()

if __name__ == "__main__":
    shell = LVMShellProxy()
    in_line = "start"
    try:
        while in_line:
            in_line = raw_input("lvm> ")
            if in_line:
                ret, out, err, = shell.call_lvm(in_line.split())
                print("RET: %d" % ret)
                print("OUT:\n%s" % out)
                print("ERR:\n%s" % err)
    except Exception:
        pass
    finally:
        print()
