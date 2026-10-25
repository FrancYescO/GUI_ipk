include $(TOPDIR)/rules.mk

PKG_NAME:=tailscale
PKG_VERSION:=1.104.2
PKG_RELEASE:=1
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://codeload.github.com/tailscale/tailscale/tar.gz/refs/tags/v$(PKG_VERSION)?
PKG_HASH:=4c1c806e16507414a1459afcdc399f6a1323c21a1ac90f07bea0465fd8fd7e1d
PKG_LICENSE:=BSD-3-Clause
PKG_LICENSE_FILES:=LICENSE
PKG_BUILD_PARALLEL:=1
TAILSCALE_GO_VERSION:=1.27.3
TAILSCALE_GO_ARCHIVE:=go$(TAILSCALE_GO_VERSION).linux-amd64.tar.gz

include $(INCLUDE_DIR)/package.mk

define Download/tailscale-go
  FILE:=$(TAILSCALE_GO_ARCHIVE)
  URL:=https://dl.google.com/go
  HASH:=65efbc80fdc1fa2cd2631cad5b481777a68e8725f34e89f50fc6ac714e379b40
endef
$(eval $(call Download,tailscale-go))

define Package/tailscale
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=VPN
  TITLE:=Tailscale client and daemon
  URL:=https://tailscale.com
  DEPENDS:=@arm +ca-bundle
endef

define Package/tailscale/conffiles
/etc/config/tailscale
endef

define Build/Prepare
	$(call Build/Prepare/Default)
	test "$(shell uname -s)-$(shell uname -m)" = Linux-x86_64
	mkdir -p $(PKG_BUILD_DIR)/.host-go
	tar -xzf $(DL_DIR)/$(TAILSCALE_GO_ARCHIVE) -C $(PKG_BUILD_DIR)/.host-go
endef

define Build/Configure
endef

define Build/Compile
	cd $(PKG_BUILD_DIR) && \
		CGO_ENABLED=0 GOOS=linux GOARCH=arm GOARM=7,softfloat \
		GOENV=off GOTOOLCHAIN=local GOFLAGS=-mod=readonly \
		GOPROXY=https://proxy.golang.org GOSUMDB=sum.golang.org \
		GOPATH=$(PKG_BUILD_DIR)/.gopath GOCACHE=$(PKG_BUILD_DIR)/.gocache \
		GOROOT=$(PKG_BUILD_DIR)/.host-go/go \
		$(PKG_BUILD_DIR)/.host-go/go/bin/go build -p 2 \
		-trimpath -buildvcs=false -tags ts_include_cli \
		-ldflags '-s -w -buildid= -X tailscale.com/version.longStamp=$(PKG_VERSION) -X tailscale.com/version.shortStamp=$(PKG_VERSION)' \
		-o $(PKG_BUILD_DIR)/tailscaled ./cmd/tailscaled
endef

define Package/tailscale/install
	$(INSTALL_DIR) $(1)/usr/sbin $(1)/usr/bin $(1)/etc/config $(1)/etc/init.d $(1)/usr/share/licenses/tailscale
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/tailscaled $(1)/usr/sbin/tailscaled
	$(LN) ../sbin/tailscaled $(1)/usr/bin/tailscale
	$(INSTALL_CONF) ./files/tailscale.config $(1)/etc/config/tailscale
	$(INSTALL_BIN) ./files/tailscale.init $(1)/etc/init.d/tailscale
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/LICENSE $(1)/usr/share/licenses/tailscale/
endef

$(eval $(call BuildPackage,tailscale))
