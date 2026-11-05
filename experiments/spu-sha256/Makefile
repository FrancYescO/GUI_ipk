obj-m := spu_sha256_hybrid.o
ccflags-y += -Werror

# Must never be enabled by the regular Actions laboratory profile.
ifeq ($(SPU_INPLACE_LAB),1)
ccflags-y += -DSPU_SHA256_INPLACE_LAB
endif
