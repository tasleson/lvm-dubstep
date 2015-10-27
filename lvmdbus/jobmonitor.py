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
import datetime

POLL_INTERVAL_SECONDS = 5


def refresh_move_objs(lvm_id, src_pv=None, dest_pv=None):
    lv = cfg.om.get_by_lvm_id(lvm_id)
    if lv:
        # Best guess is that the lv and the source & dest.
        # PV state needs to be updated, need to verify.
        utils.pprint('gen_signals: move LV %s' % (str(lvm_id)),
                                     "fg_yellow", "bg_black")
        lv.refresh()

        vg = cfg.om.get_by_path(lv.Vg)
        if vg:
            vg.refresh()

            if not src_pv and not dest_pv:
                for pv_object_path in vg.Pvs:
                    pv = cfg.om.get_by_path(pv_object_path)
                    if pv:
                        pv.refresh()
            else:
                pv = cfg.om.get_by_lvm_id(src_pv)
                if pv:
                    pv.refresh()
                pv = cfg.om.get_by_lvm_id(dest_pv)
                if pv:
                    pv.refresh()


class Monitor(object):

    def __init__(self):
        self._rlock = threading.RLock()
        self._jobs = {}

    def get(self, lv_name):
        with self._rlock:
            if lv_name in self._jobs:
                return self._jobs[lv_name][0]
            return None

    def set(self, lv_name, job):
        with self._rlock:
            self._jobs[lv_name] = (job, datetime.datetime.now())

    def delete(self, lv_name):
        with self._rlock:
            assert lv_name in self._jobs
            assert self._jobs[lv_name][0].Complete
            del self._jobs[lv_name]

    def num_jobs(self):
        with self._rlock:
            return len(self._jobs.keys())

    def finish_all(self, last_change):
        with self._rlock:
            for k in self._jobs.keys():
                v, ts = self._jobs[k]

                if (last_change - ts).seconds >= (2 * POLL_INTERVAL_SECONDS):
                    refresh_move_objs(k)
                    v.Percent = 100
                    v.Complete = True
                    del self._jobs[k]


def monitor_moves():
    prev_jobs = {}

    def gen_signals(p, c):
        if p:
            #print 'PREV=', str(p)
            #print 'CURR=', str(c)

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
                        refresh_move_objs(prev_k, state['src_dev'],
                                          state['dest_dev'])

                        job_obj = cfg.jobs.get(prev_k)
                        job_obj.Percent = 100
                        job_obj.Complete = True
                        cfg.jobs.delete(prev_k)

            # Update previous to current
            p.update(c)

    while cfg.run.value != 0:

        try:
            cfg.kick_q.get(True, POLL_INTERVAL_SECONDS)
        except IOError:
            pass
        except Queue.Empty:
            pass

        last_seen = datetime.datetime.now()

        while True:
            if cfg.run.value == 0:
                break

            cur_jobs = cmdhandler.pv_move_status()

            if cur_jobs:
                last_seen = datetime.datetime.now()
                if not prev_jobs:
                    prev_jobs = cur_jobs
                else:
                    gen_signals(prev_jobs, cur_jobs)
            else:
                #Signal any that remain in running!
                gen_signals(prev_jobs, cur_jobs)
                prev_jobs = None

                # Check to see if we have any jobs that are not making
                # progress
                with cfg.om.locked():
                    if cfg.jobs.num_jobs() > 0:
                        cfg.jobs.finish_all(last_seen)

                break

            time.sleep(1)

    return None
