#define CRYPTODEV_PIN_TEST
#include "zc.c"
#include <stdio.h>
static void clean(struct csession *s){unsigned i;release_user_pages(s);for(i=0;i<256;i++)assert(pool[i].refs==0);free(s->pages);free(s->sg);memset(s,0,sizeof(*s));pool_used=gup_calls=fail_call=partial_count=alloc_call=fail_alloc=0;}
int main(void){
 struct csession s={0};struct scatterlist *a,*b;int rc;void *src=(void*)0x10000,*dst=(void*)0x30000;
 rc=get_userbuf(&s,src,4097,src,4097,current,current->mm,&a,&b);assert(rc==0&&a==b&&s.used_pages==2);clean(&s);
 rc=get_userbuf(&s,src,4097,dst,4097,current,current->mm,&a,&b);assert(rc==0&&a!=b&&s.used_pages==4&&s.readonly_pages==2);clean(&s);
 fail_call=2;partial_count=1;rc=get_userbuf(&s,src,4097,dst,4097,current,current->mm,&a,&b);assert(rc<0&&s.used_pages==0);clean(&s);
 fail_call=1;partial_count=1;rc=get_userbuf(&s,src,4097,src,4097,current,current->mm,&a,&b);assert(rc<0&&s.used_pages==0);clean(&s);
 fail_call=1;partial_count=0;rc=get_userbuf(&s,src,4097,dst,4097,current,current->mm,&a,&b);assert(rc<0&&s.used_pages==0);clean(&s);
 /* Repeated destination failure after a successful operation must not release stale pages. */
 rc=get_userbuf(&s,src,4097,dst,4097,current,current->mm,&a,&b);assert(rc==0);release_user_pages(&s);
 fail_call=gup_calls+2;partial_count=0;rc=get_userbuf(&s,src,4097,dst,4097,current,current->mm,&a,&b);assert(rc<0&&s.used_pages==0);clean(&s);
 rc=get_userbuf(&s,NULL,16,dst,16,current,current->mm,&a,&b);assert(rc<0&&gup_calls==0);clean(&s);
 rc=get_userbuf(&s,(void*)(~0UL-7),32,dst,32,current,current->mm,&a,&b);assert(rc<0&&gup_calls==0);clean(&s);
 rc=get_userbuf(&s,src,CRYPTODEV_MAX_BYTES+8192,dst,16,current,current->mm,&a,&b);assert(rc<0&&gup_calls==0);clean(&s);
 fail_alloc=2;rc=get_userbuf(&s,src,16,dst,16,current,current->mm,&a,&b);assert(rc<0&&s.pages==NULL&&s.sg==NULL);clean(&s);
 puts("cryptodev pin ownership: 10 regression scenarios passed");return 0;
}
