Notice
=========
As of 2/17/2016 the code has been integrated with LVM git repo:
https://sourceware.org/git/?p=lvm2.git;a=tree;f=daemons/lvmdbusd

This repo remains to maintain the history of changes in development up until this point.

#### lvm-dubstep

LVM D-Bus proof of concept


##### Trying it out (lvm 2.02.132 or later is required)
1. Copy the configuration file to allow the service to run on the system bus
  * `# cp com.redhat.lvmdbus1.conf /etc/dbus-1/system.d/`
2. Run as root
  * `# ./lvmdbusd`
3. Fire up a client, such as d-feet or other and look around

##### Documentation
* The service supports introspection, this will be the most up to date
* More human digestible API format, generated from the introspection data: https://github.com/tasleson/lvm-dubstep/blob/master/api.md
