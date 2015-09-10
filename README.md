lvm-dubstep
===========

LVM D-Bus proof of concept


#### Trying it out
1. Copy the configuration file to allow service to be run on the system bus
  * `# cp com.redhat.lvm.conf /etc/dbus-1/system.d/`
2. Run as root
  * `# ./lvmdbus.py`
3. Fire up a client, such as d-feet of other and look around

#### Documentation
* The service support introspection, this will be the most up to date
* More human digestable API format, generated from the introspection data: https://github.com/tasleson/lvm-dubstep/blob/master/api.md
