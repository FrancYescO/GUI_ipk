/* Standard ethtool ioctls, deliberately restricted to disposable lab veths. */
#include <errno.h>
#include <linux/ethtool.h>
#include <linux/sockios.h>
#include <net/if.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>
int main(int argc, char **argv)
{
    static const unsigned get[] = {ETHTOOL_GTXCSUM, ETHTOOL_GTSO, ETHTOOL_GGSO, ETHTOOL_GGRO};
    static const unsigned set[] = {ETHTOOL_STXCSUM, ETHTOOL_STSO, ETHTOOL_SGSO, ETHTOOL_SGRO};
    static const char *name[] = {"tx-checksum", "tso", "gso", "gro"};
    struct ifreq req;
    struct ethtool_value value;
    unsigned i, old;
    int fd, supported = 0;
    if (argc != 2 || (strcmp(argv[1], "spua") && strcmp(argv[1], "spub"))) return 2;
    fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return 1;
    memset(&req, 0, sizeof(req));
    snprintf(req.ifr_name, sizeof(req.ifr_name), "%s", argv[1]);
    req.ifr_data = (char *)&value;
    for (i = 0; i < sizeof(get) / sizeof(get[0]); i++) {
        value.cmd = get[i]; value.data = 0;
        if (ioctl(fd, SIOCETHTOOL, &req)) {
            printf("%s %s unsupported (%d)\n", argv[1], name[i], errno); continue;
        }
        old = value.data;
        value.cmd = set[i]; value.data = 0;
        if (ioctl(fd, SIOCETHTOOL, &req)) {
            printf("%s %s set failed (%d)\n", argv[1], name[i], errno); continue;
        }
        value.cmd = get[i];
        if (ioctl(fd, SIOCETHTOOL, &req) || value.data) return 1;
        printf("%s %s %u -> 0\n", argv[1], name[i], old); supported++;
    }
    close(fd);
    return supported ? 0 : 1;
}
