/* Small known-answer test; runs only on an explicitly selected /dev/crypto. */
#include <crypto/cryptodev.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int fd;
static void check(int ok, const char *name) {
    if (!ok) { fprintf(stderr, "FAIL %s errno=%d\n", name, errno); exit(1); }
    printf("PASS %s\n", name);
}
static void info(unsigned session) {
    struct session_info_op s = {0}; s.ses = session;
    check(ioctl(fd, CIOCGSESSINFO, &s) == 0, "session info");
    printf("driver cipher=%s hash=%s\n", s.cipher_info.cra_driver_name, s.hash_info.cra_driver_name);
}
static void cbc(void) {
    unsigned char key[] = {0x2b,0x7e,0x15,0x16,0x28,0xae,0xd2,0xa6,0xab,0xf7,0x15,0x88,0x09,0xcf,0x4f,0x3c};
    unsigned char plain[] = {0x6b,0xc1,0xbe,0xe2,0x2e,0x40,0x9f,0x96,0xe9,0x3d,0x7e,0x11,0x73,0x93,0x17,0x2a};
    unsigned char expected[] = {0x76,0x49,0xab,0xac,0x81,0x19,0xb2,0x46,0xce,0xe9,0x8e,0x9b,0x12,0xe9,0x19,0x7d};
    unsigned char iv[16], input[16], output[16];
    struct session_op s = {0}; struct crypt_op c = {0}; int inplace, copy, i;
    s.cipher=CRYPTO_AES_CBC; s.keylen=sizeof(key); s.key=key;
    check(ioctl(fd,CIOCGSESSION,&s)==0,"AES-CBC session"); info(s.ses);
    c.ses=s.ses; c.len=16; c.iv=iv;
    for(copy=0;copy<2;copy++) for(inplace=0;inplace<2;inplace++) {
        memcpy(input,plain,16); c.src=input; c.dst=inplace?input:output;
        for(i=0;i<16;i++) iv[i]=i;
        c.flags=copy?COP_FLAG_NO_ZC:0; c.op=COP_ENCRYPT;
        check(ioctl(fd,CIOCCRYPT,&c)==0 && memcmp(c.dst,expected,16)==0,"AES-CBC NIST encrypt");
        c.src=c.dst; if (!inplace) c.dst=input;
        for(i=0;i<16;i++) iv[i]=i; c.op=COP_DECRYPT;
        check(ioctl(fd,CIOCCRYPT,&c)==0 && memcmp(c.dst,plain,16)==0,"AES-CBC NIST decrypt");
        printf("mode=%s buffers=%s\n",copy?"copy":"zero-copy",inplace?"in-place":"separate");
    }
    c.flags=0; c.src=NULL; c.dst=output; c.len=16;
    check(ioctl(fd,CIOCCRYPT,&c)==-1,"reject NULL input");
    c.src=input; c.len=15; check(ioctl(fd,CIOCCRYPT,&c)==-1,"reject unaligned length");
    c.ses=0; c.len=16; check(ioctl(fd,CIOCCRYPT,&c)==-1,"reject invalid session");
    check(ioctl(fd,CIOCFSESSION,&s.ses)==0,"close AES-CBC");
}
static void hash(int hmac) {
    static const unsigned char sha[] = {0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad};
    static const unsigned char hm[] = {0xb0,0x34,0x4c,0x61,0xd8,0xdb,0x38,0x53,0x5c,0xa8,0xaf,0xce,0xaf,0x0b,0xf1,0x2b,0x88,0x1d,0xc2,0x00,0xc9,0x83,0x3d,0xa7,0x26,0xe9,0x37,0x6c,0x2e,0x32,0xcf,0xf7};
    unsigned char digest[32], key[20]; struct session_op s={0}; struct crypt_op c={0};
    memset(key,0x0b,sizeof(key)); s.mac=hmac?CRYPTO_SHA2_256_HMAC:CRYPTO_SHA2_256;
    if(hmac) {s.mackey=key;s.mackeylen=sizeof(key);}
    check(ioctl(fd,CIOCGSESSION,&s)==0,"SHA256 session"); info(s.ses);
    c.ses=s.ses; c.op=COP_ENCRYPT; c.src=(unsigned char *)(hmac?"Hi There":"abc"); c.len=hmac?8:3; c.mac=digest;
    check(ioctl(fd,CIOCCRYPT,&c)==0 && memcmp(digest,hmac?hm:sha,32)==0,hmac?"HMAC-SHA256 RFC4231":"SHA256 abc");
    check(ioctl(fd,CIOCFSESSION,&s.ses)==0,"close hash");
}
static void gcm(void) {
    static const unsigned char expected[]={0x03,0x88,0xda,0xce,0x60,0xb6,0xa3,0x92,0xf3,0x28,0xc2,0xb9,0x71,0xb2,0xfe,0x78};
    static const unsigned char expected_tag[]={0xab,0x6e,0x47,0xd4,0x2c,0xec,0x13,0xbd,0xf5,0x3a,0x67,0xb2,0x12,0x57,0xbd,0xdf};
    unsigned char key[16]={0},iv[16]={0},buf[32]={0},tag[16];
    struct session_op s={0}; struct crypt_auth_op c={0};
    s.cipher=CRYPTO_AES_GCM; s.keylen=16; s.key=key;
    if(ioctl(fd,CIOCGSESSION,&s)) {printf("SKIP AES-GCM unavailable errno=%d\n",errno);return;}
    info(s.ses); c.ses=s.ses;c.op=COP_ENCRYPT;c.len=16;c.src=buf;c.dst=buf;c.iv=iv;c.iv_len=12;c.tag=tag;c.tag_len=16;
    check(ioctl(fd,CIOCAUTHCRYPT,&c)==0 && !memcmp(buf,expected,16) && !memcmp(tag,expected_tag,16),"AES-GCM NIST encrypt in-place");
    c.op=COP_DECRYPT;
    check(ioctl(fd,CIOCAUTHCRYPT,&c)==0 && !memcmp(buf,key,16),"AES-GCM NIST decrypt in-place");
    check(ioctl(fd,CIOCFSESSION,&s.ses)==0,"close AES-GCM");
}
int main(int argc,char **argv) {
    if (argc == 3 && !strcmp(argv[1], "--deny-unprivileged")) {
        check(setgid(65534)==0 && setuid(65534)==0,"drop test privileges");
        fd=open(argv[2],O_RDWR);
        check(fd == -1 && errno == EPERM,"module rejects unprivileged open with mode 0666");
        return 0;
    }
    fd=open(argc>1?argv[1]:"/dev/crypto",O_RDWR);
    if(fd<0) {perror("open crypto");return 1;}
    cbc();hash(0);hash(1);gcm();close(fd);puts("cryptodev known-answer tests passed");return 0;
}
