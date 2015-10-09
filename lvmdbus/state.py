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

from abc import ABCMeta, abstractmethod


class State(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def lvm_id(self):
        pass

    @abstractmethod
    def identifiers(self):
        pass

    @abstractmethod
    def create_dbus_object(self, path):
        pass

    def __str__(self):
        return '*****\n' + str(self.__dict__) + '\n******\n'

