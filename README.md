lvm-dubstep
===========

LVM D-Bus proof of concept


#### Trying it out (lvm 2.02.132 or later is required)
1. Copy the configuration file to allow the service to run on the system bus
  * `# cp com.redhat.lvm1.conf /etc/dbus-1/system.d/`
2. Run as root
  * `# ./lvmdbusd`
3. Fire up a client, such as d-feet or other and look around

#### Documentation
* The service supports introspection, this will be the most up to date
* More human digestible API format, generated from the introspection data: https://github.com/tasleson/lvm-dubstep/blob/master/api.md
