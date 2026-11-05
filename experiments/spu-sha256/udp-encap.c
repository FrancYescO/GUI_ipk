/* Disposable UDP-encapsulation socket for the isolated external ESP test. */
#include <arpa/inet.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
static volatile sig_atomic_t stopping;
static void stop(int sig) { (void)sig; stopping = 1; }
int main(int argc, char **argv)
{
    struct sockaddr_in local = {0}, peer = {0};
    struct timeval tv = {30, 0};
    socklen_t len = sizeof(peer);
    char data[64], addr[INET_ADDRSTRLEN];
    int fd, mode = 2;
    ssize_t received;
    unsigned long port;
    FILE *state;
    if (argc != 4) return 2;
    port = strtoul(argv[2], NULL, 10);
    if (!port || port > 65535) return 2;
    local.sin_family = AF_INET;
    local.sin_port = htons((unsigned short)port);
    if (inet_pton(AF_INET, argv[1], &local.sin_addr) != 1) return 2;
    fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0 || bind(fd, (struct sockaddr *)&local, sizeof(local))) { perror("bind"); return 1; }
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv))) return 1;
    puts("UDP_ENCAP_LISTENING"); fflush(stdout);
    for (;;) {
        len = sizeof(peer);
        received = recvfrom(fd, data, sizeof(data), 0, (struct sockaddr *)&peer, &len);
        if (received < 0) return 1;
        if (received == 9 && !memcmp(data, "SPU2PROBE", 9)) break;
    }
    if (sendto(fd, "SPU2ACK", 7, 0, (struct sockaddr *)&peer, len) != 7) return 1;
    /* Linux UDP_ENCAP=100, UDP_ENCAP_ESPINUDP=2. Socket stays in this netns. */
    if (setsockopt(fd, IPPROTO_UDP, 100, &mode, sizeof(mode))) { perror("UDP_ENCAP"); return 1; }
    if (!inet_ntop(AF_INET, &peer.sin_addr, addr, sizeof(addr))) return 1;
    state = fopen(argv[3], "w");
    if (!state) return 1;
    fprintf(state, "%s %u\n", addr, (unsigned)ntohs(peer.sin_port));
    fclose(state);
    signal(SIGTERM, stop); signal(SIGINT, stop);
    puts("UDP_ENCAP_READY"); fflush(stdout);
    while (!stopping) sleep(1);
    close(fd);
    unlink(argv[3]);
    return 0;
}
