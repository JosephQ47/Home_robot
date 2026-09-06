#include <stdio.h>
#include <sys/utsname.h>

int main(void)
{
    struct utsname system;
    if (uname(&system) != 0) {
        perror("uname");
        return 1;
    }
    printf("HI3516_APP_CHECK_OK\nkernel=%s\narchitecture=%s\n",
           system.release, system.machine);
    return 0;
}
