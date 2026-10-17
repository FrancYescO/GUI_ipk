FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bison build-essential bzip2 ca-certificates ccache cmake curl default-jdk-headless \
      file flex gawk gcc-multilib gettext git intltool libelf-dev libglib2.0-bin libncurses5-dev \
      libncursesw5-dev libssl-dev libxml-parser-perl lua5.1 openssh-client \
      openjdk-8-jdk-headless \
      patch patchelf python python3 rsync subversion swig time unzip wget xsltproc zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

# GitHub's checkout is owned by UID 1001. Several legacy CMake recipes run
# whoami while configuring and require that UID to resolve in the container.
RUN useradd --uid 1001 --no-create-home builder

WORKDIR /repo
ENTRYPOINT ["/repo/scripts/build-packages.sh"]
