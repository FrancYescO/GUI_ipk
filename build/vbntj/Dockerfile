FROM ubuntu:12.04

ENV HOME=/app \
    BUILD_USER=builder \
    BUILD_UID=1000

COPY sources.list /etc/apt/sources.list

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y \
      autoconf automake bc build-essential file gawk gettext git \
      libncurses5-dev libncursesw5-dev libssl-dev libtool m4 \
      python quilt rsync subversion sudo texinfo unzip wget xz-utils \
      zlib1g-dev xsltproc \
 && echo "foreign-architecture i386" > /etc/dpkg/dpkg.cfg.d/multiarch \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y \
      libc6:i386 libncurses5:i386 libstdc++6:i386 \
 && useradd -u "$BUILD_UID" "$BUILD_USER" \
 && echo "$BUILD_USER ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers \
 && ln -sf /bin/bash /bin/sh \
 && mkdir -p "$HOME" \
 && chmod 0777 "$HOME" \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
USER builder

CMD ["/bin/bash"]
