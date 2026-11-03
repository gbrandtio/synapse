#include <arpa/inet.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <netdb.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <stdlib.h>
#define INTERPOSE(r, o) __attribute__((used)) static struct { const void *a, *b; } i_##o __attribute__((section("__DATA,__interpose"))) = { (const void *)r, (const void *)o };
extern char **environ; 
static void out(const char *kind, const char *what) {
  const char *p = getenv("NETLOG_FILE"); if (!p) return;
  char line[512]; int n = snprintf(line, sizeof line, "%d %s %s %s\n", getpid(), getprogname(), kind, what);
  int fd = open(p, O_WRONLY | O_APPEND | O_CREAT, 0600); if (fd >= 0) { write(fd, line, n); close(fd); }
}
static void addr(const char *kind, const struct sockaddr *a) {
  char b[300] = "?"; char ip[INET6_ADDRSTRLEN] = "";
  if (!a) { out(kind, "null"); return; }
  if (a->sa_family == AF_INET) { const struct sockaddr_in *s = (const void *)a; inet_ntop(AF_INET, &s->sin_addr, ip, sizeof ip); snprintf(b, sizeof b, "%s:%d", ip, ntohs(s->sin_port)); }
  else if (a->sa_family == AF_INET6) { const struct sockaddr_in6 *s = (const void *)a; inet_ntop(AF_INET6, &s->sin6_addr, ip, sizeof ip); snprintf(b, sizeof b, "[%s]:%d", ip, ntohs(s->sin6_port)); }
  else if (a->sa_family == AF_UNIX) snprintf(b, sizeof b, "unix:%s", ((const struct sockaddr_un *)a)->sun_path);
  else snprintf(b, sizeof b, "family%d", a->sa_family);
  out(kind, b);
}
static int my_connect(int f, const struct sockaddr *a, socklen_t l) { addr("connect", a); return connect(f, a, l); }
static ssize_t my_sendto(int f, const void *m, size_t n, int fl, const struct sockaddr *a, socklen_t l) { if (a) addr("sendto", a); return sendto(f, m, n, fl, a, l); }
static int my_gai(const char *h, const char *s, const struct addrinfo *i, struct addrinfo **r) { out("getaddrinfo", h ? h : "null"); return getaddrinfo(h, s, i, r); }
static struct hostent *my_ghbn(const char *h) { out("gethostbyname", h ? h : "null"); return gethostbyname(h); }
INTERPOSE(my_connect, connect)
INTERPOSE(my_sendto, sendto)
INTERPOSE(my_gai, getaddrinfo)
INTERPOSE(my_ghbn, gethostbyname)
