#include <stdio.h>
#include <stdlib.h>
#include <systemd/sd-bus.h>

/*
 * Test if the look-up works immediately after the VG Create, written in C
 * to ensure we make this check as quick as possible.
 *
 * gcc -O2 vg_lookup.c -o vg_lookup `pkg-config --cflags --libs libsystemd`
 *
 /

int main(int argc, char *argv[]) {
        sd_bus_error error = SD_BUS_ERROR_NULL;
        sd_bus_message *m = NULL;
        sd_bus_message *lookup_m = NULL;
        sd_bus *bus = NULL;
        const char *vg_path;
        const char *job_path;
        const char *lookup_path;
        int r;

        /* Connect to the system bus */
        r = sd_bus_open_system(&bus);
        if (r < 0) {
                fprintf(stderr, "Failed to connect to system bus: %s\n", strerror(-r));
                goto finish;
        }

        /* Issue the method call and store the response message in m */
        r = sd_bus_call_method(bus,
                               "com.redhat.lvmdbus1",           /* service to contact */
                               "/com/redhat/lvmdbus1/Manager",  /* object path */
                               "com.redhat.lvmdbus1.Manager",   /* interface name */
                               "VgCreate",                      /* method name */
                               &error,                          /* object to return error in */
                               &m,                              /* return message on success */
                               "saoia{sv}",                     /* input signature */
                               "sdbus_vg",                      /* first argument */
                                2,                              /* Array size */
                                "/com/redhat/lvmdbus1/Pv/0",    /* Array element 0 */
                                "/com/redhat/lvmdbus1/Pv/1",    /* Array element 1 */
                                15,                             /* Time out */
                                0                               /* Size of dictionary */
				);
        if (r < 0) {
                fprintf(stderr, "Failed to issue method call: %s\n", error.message);
                goto finish;
        }

        /* Parse the response message */
        r = sd_bus_message_read(m, "(oo)", &vg_path, &job_path);
        if (r < 0) {
                fprintf(stderr, "Failed to parse response message from VgCreate: %s\n", strerror(-r));
                goto finish;
        }

        /* Lets ensure that the look-up shows that the VG is present */
        r = sd_bus_call_method(bus,
                               "com.redhat.lvmdbus1",           /* service to contact */
                               "/com/redhat/lvmdbus1/Manager",  /* object path */
                               "com.redhat.lvmdbus1.Manager",   /* interface name */
                               "LookUpByLvmId",                 /* method name */
                               &error,                          /* object to return error in */
                               &lookup_m,                       /* return message on success */
                               "s",                             /* input signature */
                               "sdbus_vg"                       /* first argument */
		);

        /* Parse the response message */
        r = sd_bus_message_read(lookup_m, "o", &lookup_path);
        if (r < 0) {
                fprintf(stderr, "Failed to parse look-up response message: %s\n", strerror(-r));
                goto finish;
        }    

        if (strcmp(vg_path, lookup_path) != 0) {
            printf("Expected = %s, actual = %s\n", vg_path, lookup_path);
        } else {
            printf("Look-up worked!\n");
        }

finish:
        sd_bus_error_free(&error);
        sd_bus_message_unref(m);
        sd_bus_message_unref(lookup_m);
        sd_bus_unref(bus);

        return r < 0 ? EXIT_FAILURE : EXIT_SUCCESS;
}
