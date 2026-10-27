#include <linux/bug.h>
#include <linux/init.h>
#include <linux/module.h>
#include <linux/netdevice.h>
#include <linux/skbuff.h>
#include <linux/stddef.h>
#include <linux/gen_stats.h>
#include <linux/netfilter/nf_nat.h>
#include <net/sch_generic.h>

static int __init vbntj_abi_canary_init(void)
{
	BUILD_BUG_ON(sizeof(struct net_device) != 0x4c0);
	BUILD_BUG_ON(offsetof(struct net_device, flags) != 0x1c0);
	BUILD_BUG_ON(offsetof(struct net_device, mc) +
		     offsetof(struct netdev_hw_addr_list, count) != 0x220);
	BUILD_BUG_ON(offsetof(struct net_device, _tx) != 0x2e0);
	BUILD_BUG_ON(offsetof(struct sk_buff, end) != 0x13c);
	BUILD_BUG_ON(sizeof(struct gnet_stats_basic_packed) != 12);
	BUILD_BUG_ON(sizeof(struct gnet_stats_rate_est) != 8);
	BUILD_BUG_ON(sizeof(struct gnet_stats_rate_est64) != 16);
	BUILD_BUG_ON(sizeof(struct Qdisc) != 192);
	BUILD_BUG_ON(offsetof(struct Qdisc, q) + offsetof(struct sk_buff_head, qlen) != 0x64);
	BUILD_BUG_ON(sizeof(struct nf_nat_ipv4_multi_range_compat) != 20);
	BUILD_BUG_ON(sizeof(struct nf_nat_range) != 40);
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
