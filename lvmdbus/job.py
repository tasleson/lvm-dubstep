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

from automatedproperties import AutomatedProperties
from utils import job_obj_path_generate
import cfg
from cfg import JOB_INTERFACE
import dbus
import threading


# noinspection PyPep8Naming
class Job(AutomatedProperties):
    DBUS_INTERFACE = JOB_INTERFACE
    _Percent_type = 'y'
    _Complete_type = 'b'
    _Result_type = 'o'
    _GetError_type = '(is)'

    def __init__(self, lv_name, request):
        super(Job, self).__init__(job_obj_path_generate(), JOB_INTERFACE)
        self.rlock = threading.RLock()

        self._percent = 0
        self._complete = False
        self._request = request

        # This is an lvm command that is just taking too long and doesn't
        # support background operation
        if self._request:
            # Faking the percentage when we don't have one
            self._percent = 1

        # This is a lv that is having a move in progress
        if lv_name:
            cfg.jobs.set(lv_name, self)

        assert ((self._request is None and lv_name) or
                (self._request and lv_name is None))

    @property
    def Percent(self):
        with self.rlock:
            return self._percent

    @Percent.setter
    def Percent(self, value):
        with self.rlock:
            self._percent = value

    @property
    def Complete(self):
        with self.rlock:
            if self._request:
                self._complete = self._request.is_done()
                if self._complete:
                    self._percent = 100

            return self._complete

    @Complete.setter
    def Complete(self, value):
        with self.rlock:
            self._complete = value

    @property
    def GetError(self):
        with self.rlock:
            if self.Complete:
                if self._request:
                    (rc, error) = self._request.get_errors()
                    return (rc, str(error))
                else:
                    return (0, '')
            else:
                return (-1, 'Job is not complete!')

    @dbus.service.method(dbus_interface=JOB_INTERFACE)
    def Remove(self):
        with self.rlock:
            if self.Complete:
                cfg.om.remove_object(self, True)
                self._request = None
            else:
                raise dbus.exceptions.DBusException(
                    JOB_INTERFACE, 'Job is not complete!')

    @property
    def Result(self):
        with self.rlock:
            if self._request:
                return self._request.result()
            return '/'

    @property
    def lvm_id(self):
        return str(id(self))

    @property
    def Uuid(self):
        import uuid
        return uuid.uuid1()
