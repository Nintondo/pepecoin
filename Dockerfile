FROM debian:bookworm AS builder

ARG VERSION_PEPE
ARG BUILD_JOBS=0
ARG RUN_TESTS=0
ARG PREFIX=/opt/pepecoin
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /usr/src/pepecoin

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libtool autotools-dev automake pkg-config \
    bsdmainutils curl ca-certificates ccache rsync git procps \
    bison python3 python3-pip python3-setuptools python3-wheel \
    bc tar python3-zmq python3-venv && \
    python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir setuptools==70.3.0 --upgrade && \
    /opt/venv/bin/pip install --no-cache-dir lief && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN curl -o pepecoin.tar.gz -Lk "https://github.com/pepecoinppc/pepecoin/archive/refs/tags/v${VERSION_PEPE}.tar.gz" && \
    tar -xf pepecoin.tar.gz && \
    mv pepecoin-${VERSION_PEPE}/* ./ && \
    rm -rf pepecoin-${VERSION_PEPE} && \
    rm -f pepecoin.tar.gz

RUN if [ "${BUILD_JOBS}" = "0" ] || [ -z "${BUILD_JOBS}" ]; then BUILD_JOBS="$(nproc)"; fi && \
    ln -snf /usr/share/zoneinfo/Etc/UTC /etc/localtime && echo Etc/UTC > /etc/timezone && \
    ccache --max-size=100M && \
    make -j"${BUILD_JOBS}" -C depends HOST=x86_64-unknown-linux-gnu && \
    ./autogen.sh && \
    CONFIG_SITE="$PWD/depends/x86_64-unknown-linux-gnu/share/config.site" \
    ./configure --prefix="${PREFIX}" --enable-glibc-back-compat --enable-zmq \
      --enable-reduce-exports --enable-c++14 LDFLAGS=-static-libstdc++ && \
    make -j"${BUILD_JOBS}" && \
    if [ "${RUN_TESTS}" = "1" ]; then make -j"${BUILD_JOBS}" check VERBOSE=1; fi && \
    mkdir -p /build && \
    make DESTDIR=/build install

FROM debian:bookworm-slim AS runner

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gosu \
    libc6 \
    libgcc-s1 \
    tini && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1001 appuser && \
    useradd --system --uid 1001 --gid appuser --home /home/appuser --shell /usr/sbin/nologin appuser && \
    mkdir -p /home/appuser/.cache /data && \
    chown -R 1001:1001 /home/appuser /data

WORKDIR /app

COPY --from=builder /build/opt/pepecoin/bin/ /app/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 19918

ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
CMD ["/app/pepecoind"]
