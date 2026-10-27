/* Freestanding ARM EABI userspace probe: no libc or kernel module required.
 * Attach to the test-owned ktun52 interface, inject IPv4/UDP and read the
 * kernel's ICMP port-unreachable reply. Run only inside its test namespace. */
typedef unsigned int u32;
static long call3(long number, long a, long b, long c)
{
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r7 __asm__("r7") = number;
    __asm__ volatile ("svc 0" : "+r"(r0) : "r"(r1), "r"(r2), "r"(r7) : "memory", "cc");
    return r0;
}
static void done(int code)
{
    call3(1, code, 0, 0);
    for (;;) {}
}
void _start(void)
{
    struct { char name[16]; unsigned short flags; char padding[22]; } request;
    struct { int fd; short events, revents; } pollfd;
    unsigned char packet[] = {0x45, 0x00, 0x00, 0x21, 0x00, 0x52, 0x00, 0x00, 0x40, 0x11, 0xbe, 0x51, 0xc6, 0x12, 0x98, 0x02, 0xc6, 0x12, 0x98, 0x01, 0x10, 0x92, 0x10, 0x93, 0x00, 0x0d, 0x00, 0x00, 0x54, 0x55, 0x4e, 0x35, 0x32};
    unsigned char response[256];
    const char interface[] = "ktun52";
    const char message[] = "TUN_PACKET_IO_PASS\n";
    int i, fd;
    long n;
    for (i = 0; i < (int)sizeof(request); i++) ((char *)&request)[i] = 0;
    for (i = 0; i < (int)sizeof(interface); i++) request.name[i] = interface[i];
    request.flags = 0x1001; /* IFF_TUN | IFF_NO_PI */
    fd = call3(5, (long)"/dev/net/tun", 2 | 0x800, 0);
    if (fd < 0) done(10);
    if (call3(54, fd, 0x400454ca, (long)&request) < 0) done(11);
    n = call3(4, fd, (long)packet, sizeof(packet));
    if (n != sizeof(packet)) done(12);
    pollfd.fd = fd; pollfd.events = 1; pollfd.revents = 0;
    if (call3(168, (long)&pollfd, 1, 3000) <= 0) done(13);
    n = call3(3, fd, (long)response, sizeof(response));
    call3(6, fd, 0, 0);
    if (n < 28 || (response[0] >> 4) != 4 || response[9] != 1 ||
        response[(response[0] & 15) * 4] != 3) done(14);
    call3(4, 1, (long)message, sizeof(message) - 1);
    done(0);
}
