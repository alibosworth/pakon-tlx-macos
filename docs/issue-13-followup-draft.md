I tried x87sidecar on the M1 Mac mini (macOS 26.4.1) and it fixes this. Colour saves go from about 28 s per frame to about 3.3 s, roughly 8x faster.

### Timings

Same 4-exposure strip, colour 8-bit TIFF to `P:`, timed from TLX going busy to each file landing (polled every 0.2 s):

| frame | stock Wine 11.0 | patched Wine + x87sidecar |
|---|---|---|
| 1 | 29.5 s | ~2.4 s |
| 2 | 27.3 s | 3.6 s |
| 3 | 29.1 s | 3.4 s |
| 4 | 27.5 s | 3.6 s |
| all four | 1 min 53 s | 13 s |

For a 34-frame roll that is about 2 minutes instead of 15. Files are the usual 18,000,246 bytes. The first sidecar figure is approximate: my watcher missed that file, so its time comes from the file's timestamp, which only has whole seconds.

### Setup

x87sidecar needs Wine to hand each 32-bit process over to it, which stock Wine does not do, so it takes the author's patched Wine build. That build bundles the sidecar, so it is one download:

- Wine: [athei/wine-build `cx-26.3.0-9`](https://github.com/athei/wine-build/releases/tag/cx-26.3.0-9), `wine-cx-26.3.0-9-macos-x86_64.tar.xz`, sha256 `af3682051414eeffa5be48584a671790fd3852e980ff5acd38facff6f4bff1e9`. CrossOver 26.3 sources, reports itself as `wine-11.0`, x86_64 under Rosetta, minimum macOS 15.
- The bundled `bin/x87sidecar` is byte-identical to the [x87sidecar v1.9.0](https://github.com/athei/x87sidecar/releases/tag/v1.9.0) release.

Before installing anything, the standalone release has a read-only check that tells you whether your Rosetta version is supported:

```
./x87sidecar --probe
```

On macOS 26.4.1 it printed `supported` (Rosetta 26.4 opcode table, both hooks OK).

I unpacked the Wine tarball into `~/Applications/Wine CX x87/` and ran it on an APFS clone of my prefix so the working setup stayed untouched:

```
cp -c -R -p ~/.wine ~/.wine-x87

./run.sh stop
WINEPREFIX=~/.wine-x87 \
ROSETTA_X87_PATH=~/Applications/"Wine CX x87"/wine/bin/x87sidecar \
PAKON_WINE=~/Applications/"Wine CX x87"/wine/bin/wine ./run.sh
```

`run.sh` needed no changes. To confirm the sidecar is actually in use, look for this line in `/tmp/tlxclient.log`:

```
attaching rosettax87 --cooperative (.../x87sidecar) for .../TLXClientDemo.exe
```

If it could not hook Rosetta, the log says `RUNNING WITHOUT X87 ACCELERATION` instead and TLX runs at the old speed. The binaries are ad-hoc signed rather than notarized, so they run from Terminal but Gatekeeper will refuse them if you try to open them from Finder.

### Does the output change?

The sidecar does x87 maths in 64-bit doubles instead of the x87's 80-bit format. At the precision setting Windows programs run at by default, its README says the results match the hardware, but I wanted to check against real output.

TLX wipes its roll buffers at every launch, so the same scan can't be saved under both Wines. I scanned the strip once under each, lined each pair up (the framing moved 2 to 7 px between scans) and compared them:

| frame | mean R/G/B difference, sidecar minus stock (0-255) | mean abs difference, 8x8 blocks |
|---|---|---|
| 1 | +19.8 / +19.5 / +21.8 | 20.4 |
| 2 | -2.7 / -4.1 / -3.2 | 3.7 |
| 3 | +2.2 / +1.4 / +3.5 | 3.4 |
| 4 | -0.6 / -2.2 / -0.6 | 3.5 |

Frames 2 to 4 differ by a few levels, sometimes lighter and sometimes darker, which looks like normal rescan variation plus TLX's auto balance seeing slightly different framing. Frame 1 came out about a third of a stop brighter with the sidecar. That frame has blown-out leader along one edge and shifted the most (7 px), so I think the auto balance just saw more or less of the white edge, but I haven't proven that with a second stock scan. For my use the difference is fine given the speed-up.

Raw saves were already instant on stock Wine, which suggests they do little or no x87 work, so I'd expect them to be unaffected. I haven't verified that byte for byte, since rescans differ anyway.

### Not tried

The same author also publishes `arm64-*` builds ([Mach9](https://github.com/athei/mach9)), an arm64 Wine that runs x86 code through FEX instead of Rosetta and does x87 at reduced precision by default. That might be another way round this, but it needs a fresh prefix and a full reinstall, so I stopped once the sidecar worked.
