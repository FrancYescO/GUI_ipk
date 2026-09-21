#include <linux/bug.h>
#include <linux/init.h>
#include <linux/module.h>
#include <linux/netdevice.h>
#include <linux/skbuff.h>
#include <linux/stddef.h>

static int __init vbntj_abi_canary_init(void)
{
	BUILD_BUG_ON(sizeof(struct net_device) != 0x4c0);
	BUILD_BUG_ON(offsetof(struct net_device, flags) != 0x1c0);
	BUILD_BUG_ON(offsetof(struct net_device, mc) +
		     offsetof(struct netdev_hw_addr_list, count) != 0x220);
	BUILD_BUG_ON(offsetof(struct net_device, _tx) != 0x2e0);
	BUILD_BUG_ON(offsetof(struct sk_buff, end) != 0x13c);
	return 0;
}

static void __exit vbntj_abi_canary_exit(void)
{
}

module_init(vbntj_abi_canary_init);
module_exit(vbntj_abi_canary_exit);

MODULE_DESCRIPTION("VBNTJ Damson 4.1.52 compile-time ABI canary");
MODULE_AUTHOR("GUI_ipk project");
MODULE_LICENSE("GPL");
