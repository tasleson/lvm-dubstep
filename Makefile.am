
dbusconfdir = $(sysconfdir)/dbus-1/system.d
dist_dbusconf_DATA = com.redhat.lvmdbus1.conf

dbusservicedir = $(datadir)/dbus-1/system-services
dist_dbusservice_DATA = com.redhat.lvmdbus1.service


if HAVE_SYSTEMD
systemdsystemunit_DATA = lvmdbusd.service
endif

lvmdbusdir = $(pythondir)/lvmdbus

lvmdbus_PYTHON = \
	lvmdbus/automatedproperties.py \
	lvmdbus/background.py \
	lvmdbus/cfg.py \
	lvmdbus/cmdhandler.py \
	lvmdbus/fetch.py \
	lvmdbus/__init__.py \
	lvmdbus/job.py \
	lvmdbus/loader.py \
	lvmdbus/lvmdb.py \
	lvmdbus/lvmdbus.py \
	lvmdbus/lvm_shell_proxy.py \
	lvmdbus/lv.py \
	lvmdbus/manager.py \
	lvmdbus/objectmanager.py \
	lvmdbus/pv.py \
	lvmdbus/refresh.py \
	lvmdbus/request.py \
	lvmdbus/state.py \
	lvmdbus/udevwatch.py \
	lvmdbus/utils.py \
	lvmdbus/vg.py

dist_sbin_SCRIPTS = lvmdbusd

lsmdbusd_MANS = lvmdbus.8
