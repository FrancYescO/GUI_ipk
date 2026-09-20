# Linux 4.1.52 vendor rebase

`vendor-linux-stable-4.1.38-to-4.1.52.patch.gz` contains the official Linux
stable changes from 4.1.38 through 4.1.52, rebased onto the Technicolor
VANTW/VBNTS patch stack.

It was produced by a three-way merge using these upstream archives:

- `linux-4.1.38.tar.xz`:
  `b8c23117cb08cb0bfc9660375130caaee2fabb39bc5d680557d4521e7e08bd56`
- `linux-4.1.52.tar.xz`:
  `6ad9389e55e0ea57768eae173747058a4487fa3630e10a7999cfec9f945e559c`

The common ancestor was vanilla 4.1.38, the vendor side was the complete
Technicolor patch stack, and the stable side was vanilla 4.1.52. Overlapping
network changes retain the Broadcom and MPTCP interfaces while incorporating
the 4.1.52 fixes. Stable changes already present in vendor backports are not
applied twice.

Compressed patch SHA-256:

```text
4aff15246f2215981f3a835bc44150e5a81f1593c16e6971924a86cee5f167b8
```

The build starts from the verified 4.1.38 archive, applies the vendor patches,
then applies this rebased delta. This is necessary because the large Broadcom
base patch does not apply directly to a pristine 4.1.52 tree.
