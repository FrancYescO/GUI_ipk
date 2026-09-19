FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bison build-essential bzip2 ca-certificates ccache cmake curl file flex gawk gettext git \
      libelf-dev libncurses5-dev libncursesw5-dev libssl-dev \
      patchelf python python3 rsync subversion swig time unzip wget xsltproc zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /repo
ENTRYPOINT ["/repo/scripts/build-packages.sh"]
