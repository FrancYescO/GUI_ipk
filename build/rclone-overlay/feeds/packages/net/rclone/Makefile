include $(TOPDIR)/rules.mk

PKG_NAME:=rclone
PKG_VERSION:=1.75.2
PKG_RELEASE:=1
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://codeload.github.com/rclone/rclone/tar.gz/refs/tags/v$(PKG_VERSION)?
PKG_HASH:=68afd7f68c84bd978966feae2116339aa7bf454b39c573910c462e87c3774d5a
PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=COPYING
PKG_BUILD_PARALLEL:=1

# This isolated host toolchain leaves the archived Go 1.10 recipes unchanged.
RCLONE_GO_VERSION:=1.26.10
RCLONE_GO_ARCHIVE:=go$(RCLONE_GO_VERSION).linux-amd64.tar.gz

include $(INCLUDE_DIR)/package.mk

define Download/rclone-go
  FILE:=$(RCLONE_GO_ARCHIVE)
  URL:=https://dl.google.com/go
  HASH:=ccfe7ae822d2c2f41f4fe7c956199967a4dac22d0ee0d2b2bfdb440aab3b20c5
endef
$(eval $(call Download,rclone-go))

define Package/rclone
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=File Transfer
  TITLE:=Rclone cloud storage client
  URL:=https://rclone.org
  DEPENDS:=@arm +ca-bundle
  USERID:=rclone:rclone
endef

define Package/rclone-config
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=File Transfer
  TITLE:=Disabled-by-default Rclone remote-control service
  DEPENDS:=+rclone
endef

define Package/rclone-config/conffiles
/etc/config/rclone
/etc/rclone/rclone.conf
endef

define Build/Prepare
	$(call Build/Prepare/Default)
	test "$$(uname -s)-$$(uname -m)" = Linux-x86_64
	mkdir -p $(PKG_BUILD_DIR)/.host-go
	tar -xzf $(DL_DIR)/$(RCLONE_GO_ARCHIVE) -C $(PKG_BUILD_DIR)/.host-go
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
		-trimpath -buildvcs=false -tags noselfupdate \
		-ldflags '-s -w -buildid= -X github.com/rclone/rclone/fs.Version=v$(PKG_VERSION)' \
		-o $(PKG_BUILD_DIR)/rclone .
endef

define Package/rclone/install
	$(INSTALL_DIR) $(1)/usr/bin $(1)/usr/share/licenses/rclone
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/rclone $(1)/usr/bin/rclone
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/COPYING $(1)/usr/share/licenses/rclone/
endef

define Package/rclone-config/install
	$(INSTALL_DIR) $(1)/etc/config $(1)/etc/init.d $(1)/etc/rclone
	$(INSTALL_CONF) ./files/rclone.config $(1)/etc/config/rclone
	$(INSTALL_BIN) ./files/rclone.init $(1)/etc/init.d/rclone
	touch $(1)/etc/rclone/rclone.conf
	chmod 600 $(1)/etc/rclone/rclone.conf
endef

$(eval $(call BuildPackage,rclone))
$(eval $(call BuildPackage,rclone-config))
