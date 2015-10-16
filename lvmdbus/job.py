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
import cmdhandler
import dbus


# noinspection PyPep8Naming
class Job(AutomatedProperties):
    DBUS_INTERFACE = JOB_INTERFACE
    _percent_type = 'y'
    _is_complete_type = 'b'
    _result_type = 'o'
    _get_error_type = '(is)'

    def __init__(self, lv_name):
        super(Job, self).__init__(job_obj_path_generate(), JOB_INTERFACE)
        self._lv_name = lv_name

    @property
    def percent(self):
        current = cmdhandler.pv_move_status()
        if self._lv_name in current:
            return current[self._lv_name]['percent']
        return 100

    @property
    def is_complete(self):
        current = cmdhandler.pv_move_status()
        if self._lv_name not in current:
            return True
        return False

    @property
    def get_error(self):
        if self.is_complete:
            return (0, '')
        else:
            return (-1, 'Job is not complete!')

    @dbus.service.method(dbus_interface=JOB_INTERFACE)
    def Remove(self):
        if self.is_complete:
            cfg.om.remove_object(self, True)
        else:
            raise dbus.exceptions.DBusException(
                JOB_INTERFACE, 'Job is not complete!')

    @property
    def result(self):
        return '/'

    @property
    def lvm_id(self):
        return str(id(self))

    @property
    def Uuid(self):
        import uuid
        return uuid.uuid1()


# noinspection PyPep8Naming
class AsyncJob(AutomatedProperties):
    DBUS_INTERFACE = JOB_INTERFACE
    _percent_type = 'y'
    _is_complete_type = 'b'
    _result_type = 'o'
    _get_error_type = '(is)'

    def __init__(self, request):
        super(AsyncJob, self).__init__(job_obj_path_generate(),
                                       JOB_INTERFACE)
        self._request = request
        self._percent = 1

    @property
    def percent(self):
        return self._percent

    @property
    def is_complete(self):
        done = self._request.is_done()
        if done:
            self._percent = 100
        return done

    @property
    def get_error(self):
        if self.is_complete:
            (rc, error) = self._request.get_errors()
            return (rc, str(error))
        else:
            return (-1, 'Job is not complete!')

    @dbus.service.method(dbus_interface=JOB_INTERFACE)
    def Remove(self):
        if self.is_complete:
            cfg.om.remove_object(self, True)
            self._request = None
        else:
            raise dbus.exceptions.DBusException(
                JOB_INTERFACE, 'Job is not complete!')

    @property
    def result(self):
        return self._request.result()

    @property
    def lvm_id(self):
        return str(id(self))

    @property
    def Uuid(self):
        import uuid
        return uuid.uuid1()
