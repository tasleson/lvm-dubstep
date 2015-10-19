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

import threading
import Queue
import cfg
import utils
import cmdhandler
import time


class Monitor(object):

    def __init__(self):
        self._rlock = threading.RLock()
        self._jobs = {}

    def get(self, lv_name):
        with self._rlock:
            if lv_name in self._jobs:
                return self._jobs[lv_name]
            return None

    def set(self, lv_name, job):
        with self._rlock:
            self._jobs[lv_name] = job

    def delete(self, lv_name):
        with self._rlock:
            assert lv_name in self._jobs
            assert self._jobs[lv_name].Complete
            del self._jobs[lv_name]


def monitor_moves(obj_mgr):
    prev_jobs = {}

    def gen_signals(p, c):
        if p:
            print 'PREV=', str(p)
            print 'CURR=', str(c)

            for prev_k, prev_v in p.items():
                if prev_k in c:
                    if prev_v['src_dev'] == c[prev_k]['src_dev']:
                        prev_v['percent'] = c[prev_k]['percent']

                        j = cfg.jobs.get(prev_k)
                        j.Percent = int(c[prev_k]['percent'])
                    else:
                        p[prev_k] = c[prev_k]
                    del c[prev_k]
                else:
                    state = p[prev_k]
                    del p[prev_k]

                    # This move is over, update the job object and generate
                    # signals
                    with cfg.om.locked():
                        # Best guess is that the lv and the source & dest.
                        # PV state needs to be updated, need to verify.
                        utils.pprint('gen_signals %s' % (str(state)),
                                     "fg_yellow", "bg_black")

                        lv = obj_mgr.get_by_lvm_id(prev_k)
                        if lv:
                            lv.refresh()

                            vg = obj_mgr.get_by_path(lv.Vg)
                            if vg:
                                vg.refresh()

                        pv = obj_mgr.get_by_lvm_id(state['src_dev'])
                        if pv:
                            pv.refresh()
                        pv = obj_mgr.get_by_lvm_id(state['dest_dev'])
                        if pv:
                            pv.refresh()

                        job_obj = cfg.jobs.get(prev_k)
                        job_obj.Percent = 100
                        job_obj.Complete = True
                        cfg.jobs.delete(prev_k)

            # Update previous to current
            p.update(c)

    while cfg.run.value != 0:
        try:
            cfg.kick_q.get(True, 5)
        except IOError:
            pass
        except Queue.Empty:
            pass

        while True:
            if cfg.run.value == 0:
                break

            cur_jobs = cmdhandler.pv_move_status()

            if cur_jobs:
                if not prev_jobs:
                    prev_jobs = cur_jobs
                else:
                    gen_signals(prev_jobs, cur_jobs)
            else:
                #Signal any that remain in running!
                gen_signals(prev_jobs, cur_jobs)
                prev_jobs = None
                break

            time.sleep(1)

    return None
