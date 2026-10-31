# Working notes: slow colour-processed saves (started 28 Oct 2026)

Session notes so this can be picked up cold. Not upstream documentation.

**Current state (31 Oct, end of session):** the ~25 s per colour frame is
Kodak's x87 floating-point code running through Rosetta 2's software x87
emulator (profiled: ~95% of busy time inside Rosetta). Same on the M1 laptop
(macOS 15.7.7) and the M1 Mac mini (Tahoe), on Wine 9.0 / 11.0 / 11.20, with
either set of MS runtime DLLs. Ali no longer believes he ever saw fast
colour saves (earlier fast saves were raw), so this is a fundamental cost of
running Kodak's code under Rosetta, not a regression. Reported upstream as
such (draft: `docs/issue-draft-slow-colour-saves.md`). Next: try x87sidecar on the mini
(see "Next steps").

## Symptom

On an M1 MacBook Pro (MacBookPro17,1), saving **colour-processed 8-bit TIFFs** from
TLXClientDemo takes ~26 s per frame, very steady (34-frame rolls at Base 16,
3000x2000, 18 MB TIFFs). Scanning is normal speed. Saving raw is instant.
Previous use (this M1 or an M1 Mac mini) was not this slow.

During a save, `TLXClientDemo.exe` sits at ~99% of one core. The TIFF write itself
takes ~0.2 s; the rest is computation before the write (Kodak colour pipeline:
PakonIMAu / Ansel, kodakcms, etc).

## Ruled out

- USB / scanner link: `pakonusb.py` idle (~0.3% CPU) during saves.
- Debug logging: `/tmp/tlxclient.log` does not grow during saves.
- Digital ICE: off (`LED CURRENT ... IR=0` in the server log).
- iCloud Desktop sync: not enabled; saves go to `~/Desktop/pakon-scans` via `P:`.
- Power / thermal: on AC, Low Power Mode off, no thermal warnings.
- Wine version: same ~26 s on Wine 9.0 and Wine 11.0. Also Gcenx
  `wine-devel` 11.20 (31 Oct, sha256 `33bbe09a...7195ad7`, unpacked to
  `~/Applications/Wine Devel.app`), run on an APFS clone of the prefix at
  `~/.wine-11.20`, default DLLs: colour JPEG ~24 s (busy 15:01:01, written
  15:01:25). Launch: `WINEPREFIX=~/.wine-11.20 PAKON_WINE=~/Applications/"Wine Devel.app"/Contents/Resources/wine/bin/wine ./run.sh`
- Ansel cache: `anselinstalldir/anselCacheDir` and `anselTempDir` stay empty
  through a whole save (watched every 0.2 s for 3 min / 8 frames).
- Colour/save settings (sharpening, grain/noise reduction, scene balance etc):
  the same as when saves were fast (confirmed by Ali, 31 Oct).

## Suspects as of 28 Oct (both since resolved, see below)

- The whole OEM tree and its registry keys were reinstalled on 28 Oct (15:12 / 15:15)
  by `./run.sh install`, from the public archive (doctor shows mfc71u, msvcp71,
  msvcr71 as DIFFERENT from the manifest). The earlier fast install may have
  been a different copy of the files.
- Which DLL burns the time is unknown.

## Fresh test, 31 Oct

4-exposure strip, fresh scan, Wine 11, colour 8-bit TIFF to `P:`
(18,000,246 bytes each). TLX at ~100% of one core from 13:53:57:

| frame | landed       | time   |
|-------|--------------|--------|
| 1A    | 13:54:22.55  | ~25 s  |
| 2A    | 13:54:48.38  | 25.8 s |
| 3A    | 13:55:13.94  | 25.6 s |
| 4A    | 13:55:39.80  | 25.9 s |

Same ~26 s/frame as on 28 Oct. "Move oldest roll to Save Group" took ~3 s.

The roll buffers were cloned before the move to the Save Group:
`~/.wine/drive_c/Buffers-snapshot-2026-10-31-1352/PFS00.bin` + `PFS01.bin`
(`PFS00` sha1 `4486f70b...a6b2`, ~160 MB allocated, sparse). Not yet tested
whether restoring them lets TLX reload the strip.

**Answered 31 Oct 14:43: no.** TLX recreates both `PFS00.bin` / `PFS01.bin`
empty (0 blocks allocated) at every launch, so neither the Scan Group nor the
Save Group survives a restart, and a restored snapshot would be wiped too.
Within one TLX session, re-saving the strip from the Save Group is the way
to repeat a test. Across restarts it means a rescan, or the record/replay idea
in `pakonusb.py`.

Format does not matter (Ali, 31 Oct): JPEG and TIFF are both slow with colour
processing on. The same formats without colour balancing save fast, but come
out as negatives. So the time goes into the colour/inversion step itself.

## The three "DIFFERENT" runtime DLLs (checked 31 Oct)

The app-folder copies (which Wine loads: no DllOverrides, so native first) are
all Microsoft **retail** builds, version **7.10.6030.0** (VS .NET 2003 SP1),
not debug builds. Hash and size differ from `setup/manifest.json` (msvcr71
348160 = same size, other hash; msvcp71 503808 vs 499712; mfc71u 1053184 vs
1047552), which fits the manifest describing a different release, e.g. RTM
7.10.3052. Unlikely to explain a ~25x slowdown. `system32` / `syswow64`
copies are Wine builtins.

**Correction (31 Oct, via `lsof` on the running TLX):** by default Wine does
NOT load the app-folder `msvcr71.dll` / `msvcp71.dll`. It uses its own
builtins (`wine/lib/wine/i386-windows/`). Only `mfc71u.dll` and the Kodak DLLs
come from the app folder. So the "DIFFERENT" runtime hashes never affected
anything. To test the Microsoft runtime, force it:
`WINEDLLOVERRIDES="msvcr71,msvcp71=n,b"` (confirmed loading
`Server/msvcr71.dll` with that set). The original 28 Oct `msvcr71.dll` is
backed up in `Program Files/Pakon/dll-backup-2026-10-31/`; the app folder now
holds the manifest copy.

**Result (31 Oct 14:46): no change.** Fresh rescan, TLX launched with
`WINEDLLOVERRIDES="msvcr71,msvcp71=n,b"` (lsof confirmed both loading from
`Server/`, manifest `msvcr71`). First colour save (`00.jpg`) still took
~25 s from TLX going busy. C runtime ruled out: the x87 work is in the Kodak
DLLs themselves.

14:49: also swapped in the manifest `mfc71u.dll` (28 Oct copy backed up
next to `msvcr71` in `dll-backup-2026-10-31/`). Relaunched with the same
override; lsof shows all three from `Server/`: manifest `msvcr71` + manifest
`mfc71u` + 28 Oct `msvcp71` (manifest copy not obtained).
**Result: no change.** Colour TIFF `00.tif`: busy from 14:49:45, landed
14:50:10.7, ~25 s. DLLs ruled out (bar the unlikely manifest `msvcp71`).

**Why the manifest and the download disagree (31 Oct):** an official
"Pakon 135 v3.0" install CD from archive.org (`PAKONF135.iso`, Ali's
Downloads) carries BOTH builds of each MS runtime. The installer-root copies
(`/` and `fx35install/`) are the SP1 7.10.6030 build that `fetch-oem.sh`
installed. The `program files/Pakon/` (and `IQ/`) copies match the manifest
exactly. `fetch-oem.sh` sweeps the installer root for DLLs, so it picks the
setup program's copies rather than the application's. All Kodak binaries on
the CD are byte-identical to the install and the manifest; `TLB.dll` and
`tlx.dll` match the manifest on the CD (the install's are patched).

FileVersions: manifest set = `msvcr71` 7.10.3052.4, `msvcp71` 7.10.3077.0,
`mfc71u` 7.10.3077.0 (VS .NET 2003 RTM era). 28 Oct set = all 7.10.6030.0
(SP1).

14:55: manifest `msvcp71.dll` from the CD swapped in too (28 Oct copy in
`dll-backup-2026-10-31/`). All three manifest DLLs now load from `Server/`
with `WINEDLLOVERRIDES="msvcr71,msvcp71=n,b"`.
**Result: no change.** Fresh rescan, colour TIFF `00.tif` busy from ~14:55:13,
written 14:55:38, ~25 s.

**DLL conclusion (31 Oct):** ruled out. Every combination saves at ~25 s/frame:
Wine builtin `msvcr71`/`msvcp71` (the default); native 7.10.6030 (SP1); native
manifest `msvcr71`; and all three manifest DLLs (7.10.3052.4 / 7.10.3077.0)
together. The x87 work is in Kodak's own code, which matches the CD
byte-for-byte.

To undo the swap: copy the three files in `dll-backup-2026-10-31/` back into
`F-X35 COM Server/`. It makes no difference to speed, and Wine uses its
builtin `msvcr71`/`msvcp71` anyway unless the override is set.

### Hashes for the swap test

All in `~/.wine/drive_c/Program Files/Pakon/F-X35 COM Server/`.

| DLL | | sha256 | bytes |
|---|---|---|---|
| `mfc71u.dll`  | manifest  | `0c58f682e1b3af064963dd616e80609006e9317f2fcb0f3a51ed32fef13b1081` | 1047552 |
|               | installed 28 Oct | `d67a5313750093ad58fe44fcde2f255aea58d4051ae3bec73acffa5c7c8aa04b` | 1053184 |
| `msvcp71.dll` | manifest  | `df96156f6a548fd6fe5672918de5ae4509d3c810a57bffd2a91de45a3ed5b23b` | 499712 |
|               | installed 28 Oct | `6c483cbe349863c7dcf6f8cb7334e7d28c299e7d5aa063297ea2f62352f6bdd9` | 503808 |
| `msvcr71.dll` | manifest  | `8094af5ee310714caebccaeee7769ffb08048503ba478b879edfef5f1a24fefe` | 348160 |
|               | installed 28 Oct | `c4d4339df314a27ff75a38967b7569d9962337b8d4cd4b0db3aba5ff72b2bfbb` | 348160 |

Manifest-matching `mfc71u.dll` downloaded 31 Oct to
`~/Downloads/MFC71u_32-bit/MFC71u.dll` (hash confirmed). Manifest-matching
`msvcr71.dll` at `~/Downloads/msvcr71.dll` (hash confirmed).

## Suspect: Rosetta and x87 floating point

Gcenx Wine on Apple Silicon is x86_64 under Rosetta 2, with TLX's 32-bit code
running through WoW64. Code built with VC7.1 does its float maths on the x87
FPU, and x87 is Rosetta's known slow path. Rough check: 26 s for a 6 Mpx
frame is ~4 µs (~12k cycles) per pixel. Open question: what macOS and Wine
(version, wow64 or old 32-bit mode, CrossOver?) were in use when saves were
fast. If those changed, a Rosetta or Wine-mode change could be the whole
cause. `sample` on TLX during a save may show Rosetta runtime frames, which
would be direct evidence.

## Profile result (31 Oct, 14:03): the time is Rosetta's x87 emulation

macOS `sample` on TLX (pid 4182) for 10 s during a single-frame colour save,
plus `vmmap` to place the addresses. TLX survived it (unlike `winedbg`).
Sample reports `Code Type: X86-64 (translated)`. Hot addresses on the busy
thread, idle waits excluded (7,539 samples):

| where                                              | share |
|----------------------------------------------------|-------|
| `/Library/Apple/usr/libexec/oah/libRosettaRuntime` | 66.0% |
| `/usr/libexec/rosetta/runtime`                     | 29.5% |
| Rosetta JIT (the translated TLX/Kodak code itself) |  4.5% |

`libRosettaRuntime` is stripped, but its strings are Rosetta's x87 library
(`rosetta::runtime::library::x87_fadd_f64`, `x87_fmul_ST`, `x87_fpatan`,
`x87_fyl2xp1`, `X87State` ...). The hottest address (+0x1599c) sits next to
the literals `AdditionMultiplication.cpp` / `fma_rs`, i.e. software
extended-precision add/multiply. So the Kodak colour code does its maths on
the x87 FPU, and Rosetta runs each x87 instruction as a call into a software
float emulator. That is why the save takes ~25 s.

The fast runs may have been on an M1 Mac mini (2020, 16 GB) or this M1
laptop (Ali, 31 Oct). Same chip, same Rosetta, and memory is not a factor
(TLX footprint 156 MB, peak 263 MB), so hardware does not explain it.

Still unexplained: why it was fast before. Rosetta has always emulated x87,
so something else must have differed then (macOS/Rosetta version, Wine build
or mode, hardware, or a code path in the Kodak DLLs that avoids x87, e.g.
chosen by CPUID or the FPU precision setting). Unverified ideas.

Raw files: `/private/tmp/claude-501/.../scratchpad/sample.txt` and
`vmmap-before.txt` (temporary; rerun `sample <pid> 10 1 -mayDie -file ...`
during a save to regenerate).

## Leads for a fix: faster x87 under Rosetta (31 Oct)

- **athei/x87sidecar** (MIT, active, preferred): translates x87 blocks to
  ARM64 in a separate native process via a small hook in Rosetta's
  `translate_insn`. "Cooperative" mode for Wine needs no root/entitlements.
  Computes in binary64, which matches hardware at 53-bit precision control
  (the Windows default). Tested on macOS 26/27; we are on 15.7.7, so run
  `x87sidecar_entitled --probe` first. Wine integration needs athei's patched
  Wine (`athei/wine-build`, branches `cx-*-patched` in `athei/wine`), which
  re-execs 32-bit processes through `x87sidecar --cooperative` when
  `ROSETTA_X87_PATH` is set.
- **Lifeisawful/rosettax87** (MIT, archived 2 Jan 2026; continued at
  WineAndAqua/rosettax87): faster, less precise x87 handlers, ~4-5x; needs a
  root helper; README lists macOS 15.5.

Either way, compare one colour frame against a stock save for differences.

## Checklist: same test on the M1 Mac mini (planned 31 Oct)

Same chip as the laptop; the mini runs the latest macOS, so this isolates
macOS/Rosetta.

1. Record: `sw_vers`, `pkgutil --pkg-info com.apple.pkg.RosettaUpdateAuto`,
   and `wine --version` for whichever Wine `run.sh` picks up there. Also
   `ls -la /Library/Apple/usr/libexec/oah/` and
   `shasum -a 256 /Library/Apple/usr/libexec/oah/libRosettaRuntime`.
   Laptop: macOS 15.7.7 (24G720), RosettaUpdateAuto 1.0.0.0.1.1777570176,
   `libRosettaRuntime` dated 20 Jul 2025, sha256 `365aa20e63b8cc09...`.
2. Fresh scan of the 4-exposure strip, move to Save Group, save ONE colour
   8-bit TIFF. Time it (TLX going to ~100% CPU until the file lands). Laptop
   reference: ~25 s on macOS 15.7.7.
3. If slow, profile it the same way while it saves:
   `sample $(pgrep -f TLXClientDemo.exe | head -1) 10 1 -mayDie -file ~/Desktop/sample.txt`
   and `vmmap <same pid> > ~/Desktop/vmmap.txt`. Look for `libRosettaRuntime`
   in the hot addresses (the laptop showed 66%).
4. If fast, run the same `sample` anyway to see what changed.

**Result (31 Oct): just as slow on the Mac mini**, macOS Tahoe (26), Wine
11.0 (Ali). So macOS / Rosetta version is ruled out too. Every setup tested
since 28 Oct is slow; the "it used to be fast" memory is now the odd one out.

**Likely resolution (Ali, 31 Oct):** the earlier fast saves may all have
been raw. Ali may never have saved colour-processed ("normal") before. If
so, nothing regressed: colour saves have always cost ~25 s/frame on Apple
Silicon, because Kodak's x87 maths runs through Rosetta's software x87
emulator. The problem becomes a speed-up, not a regression hunt.

## Next steps (as of 31 Oct, picking up on the Mac mini)

1. **x87sidecar on the Mac mini** (macOS Tahoe, the platform it is tested
   on). See "Leads for a fix" above. Order: read the code; run
   `x87sidecar_entitled --probe` (read-only support check); if supported,
   install athei's patched Wine (`athei/wine-build`), point `ROSETTA_X87_PATH`
   at the flat `x87sidecar` binary, run TLX on a cloned prefix
   (`cp -c -R -p ~/.wine ~/.wine-x87`), time one colour save, and compare the
   output against a stock save of the same frame.
2. Workaround meanwhile: save raw and invert outside TLX.
3. Dead ends, do not repeat: roll-buffer snapshots (TLX wipes them at
   launch), `winedbg` (crashes TLX), swapping the MS runtime DLLs, other Wine
   versions, other macOS versions.

## Wine on this machine

- Homebrew disabled the `wine-stable` cask on 2026-09-01 (Gatekeeper). Reported
  on upstream issue #3, follow-up comment posted 28 Oct:
  https://github.com/pablonavarrob/pakon-tlx-macos/issues/3#issuecomment-6484615409
- Wine 11.0 installed by hand at `~/Applications/Wine Stable.app` from Gcenx
  `wine-stable-11.0_1-osx64.tar.xz` (sha256 `b50dc50e...cb82388`, matches the
  cask), quarantine cleared.
- Old Wine 9.0 is still at `/Applications/Wine Stable.app`, and `bootstrap.sh`
  checks `/Applications` first, so launch with:

  ```
  ./run.sh stop
  PAKON_WINE=~/Applications/"Wine Stable.app"/Contents/Resources/wine/bin/wine ./run.sh
  ```

## Other things seen on 28 Oct

- First launch gave `EC_NoScannerDetected`: the scanner dropped its firmware
  (re-enumerated, bus 1 to bus 0) between server start and client connect, while
  `./run.sh install` was running Wine in another terminal. The server recovered;
  relaunching TLX fixed it. Cause not confirmed.
- TLX error log at 16:50 shows `EC_WIN_DeviceIoControl Invalid function` and
  `EC_HardwareFault` around a stop/restart. Not investigated.
