AC_INIT([LVM dbus service], [1.0.0])

AC_CONFIG_MACRO_DIR([m4])

AM_INIT_AUTOMAKE([subdir-objects])

AM_PATH_PYTHON([3])
AC_PYTHON_MODULE([pyudev], [Required])
AC_PYTHON_MODULE([dbus], [Required])

AC_CONFIG_FILES([Makefile])

AC_PATH_PROG(LVM_PATH, lvm)
if test -n "$LVM_PATH"; then
	AC_DEFINE_UNQUOTED([LVM_PATH], ["$LVM_PATH"])
fi

#Setup the unit directory for systemd stuff
PKG_PROG_PKG_CONFIG
AC_ARG_WITH([systemdsystemunitdir],
        AS_HELP_STRING([--with-systemdsystemunitdir=DIR], [Directory for systemd service files]),
        [], [with_systemdsystemunitdir=$($PKG_CONFIG --variable=systemdsystemunitdir systemd)])
if test "x$with_systemdsystemunitdir" != xno; then
        AC_SUBST([systemdsystemunitdir], [$with_systemdsystemunitdir])
fi
AM_CONDITIONAL(HAVE_SYSTEMD, [test -n "$with_systemdsystemunitdir" -a "x$with_systemdsystemunitdir" != xno ])

AC_OUTPUT(lvmdbus/path.py)
