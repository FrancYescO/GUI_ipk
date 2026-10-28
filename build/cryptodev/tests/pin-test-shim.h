#ifndef CRYPTODEV_PIN_SHIM
#define CRYPTODEV_PIN_SHIM
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <errno.h>
#define __user
#define KERNEL_VERSION(a,b,c) (((a)<<16)|((b)<<8)|(c))
#define LINUX_VERSION_CODE KERNEL_VERSION(4,1,52)
#define PAGE_SHIFT 12
#define PAGE_SIZE (1UL<<PAGE_SHIFT)
#define PAGE_MASK (~(PAGE_SIZE-1))
#define GFP_KERNEL 0
#define unlikely(x) (x)
#define likely(x) (x)
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define ddebug(...) ((void)0)
#define derr(...) ((void)0)
#define dwarning(...) ((void)0)
#define down_read(x) ((void)0)
#define up_read(x) ((void)0)
struct page {int refs;};
struct scatterlist {struct page *page;unsigned int len;};
struct mm_struct {int mmap_sem;};
struct task_struct {struct mm_struct *mm;};
struct csession {unsigned int array_size,used_pages,readonly_pages;struct page **pages;struct scatterlist *sg;};
static struct mm_struct fake_mm;
static struct task_struct fake_task={&fake_mm};
#define current (&fake_task)
static struct page pool[256];
static int pool_used,gup_calls,fail_call,partial_count,alloc_call,fail_alloc;
static void *test_calloc(size_t n,size_t size) {alloc_call++;return alloc_call==fail_alloc?NULL:calloc(n,size);}
#define kcalloc(n,s,f) test_calloc(n,s)
#define kfree(p) free(p)
static void put_page(struct page *p){assert(p && p->refs==1);p->refs--;}
#define PageReserved(p) 0
#define SetPageDirty(p) ((void)0)
#define flush_dcache_page(p) ((void)0)
static void sg_init_table(struct scatterlist *s,unsigned n){memset(s,0,n*sizeof(*s));}
#define sg_mark_end(s) ((void)0)
static void sg_set_page(struct scatterlist *s,struct page *p,unsigned n,unsigned off){(void)off;s->page=p;s->len=n;}
static struct scatterlist *sg_next(struct scatterlist *s){return s+1;}
static struct scatterlist *sg_last(struct scatterlist *s,unsigned n){return s+n-1;}
static int get_user_pages(struct task_struct *t,struct mm_struct *m,unsigned long addr,unsigned count,int w,int force,struct page **pages,void *vma) {
 unsigned i,n=count;(void)t;(void)m;(void)addr;(void)w;(void)force;(void)vma;
 gup_calls++;if(gup_calls==fail_call)n=partial_count;
 for(i=0;i<n;i++){assert(pool_used<256);pages[i]=&pool[pool_used++];pages[i]->refs++;}
 return n;
}
#include "zc.h"
#endif
