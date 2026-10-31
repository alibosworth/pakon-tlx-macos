Draft issue for pablonavarrob/pakon-tlx-macos (not posted yet).

Title: Colour-processed saves take about 25 s per frame on Apple Silicon (Kodak's x87 maths under Rosetta)

---

Saving colour-processed images from TLXClientDemo takes about 25 s per frame on Apple Silicon. Raw saves are instant. For a 34-frame roll at Base 16 (3000x2000) that is about 15 minutes per roll. Scanning speed is normal.

I spent a while assuming something on my machine had regressed, but I now think it is a fixed cost of running the Kodak colour pipeline through Rosetta 2, so it probably affects everyone using this on an M-series Mac. Reporting it here so it is written down, and in case it is worth a line in the README.

What I see

- 4-exposure strip, colour 8-bit TIFF to `P:` (18 MB each): 25.0, 25.8, 25.6 and 25.9 s per frame. JPEG takes the same time, so the time is in the colour/inversion step, not the file write.
- `TLXClientDemo.exe` sits at about 100% of one core for the whole save. `pakonusb.py` is idle, so it is not the USB link.

Things I ruled out (all still about 25 s)

- Two machines with the same chip: M1 MacBook Pro on macOS 15.7.7, and M1 Mac mini on macOS 26 (Tahoe).
- Wine 9.0, 11.0 (Gcenx wine-stable) and 11.20 (Gcenx wine-devel, on a cloned prefix).
- The MS runtime DLLs from #1, in every combination: Wine's builtin `msvcr71`/`msvcp71` (the default), the 7.10.6030 (SP1) copies `fetch-oem.sh` installs, and the 7.10.3052/3077 copies that match `setup/manifest.json`, forced native with `WINEDLLOVERRIDES="msvcr71,msvcp71=n,b"`.
- Digital ICE off, colour settings unchanged, no debug logging, Ansel cache dirs stay empty.

Where the time goes

I profiled a save with macOS's `sample` (10 s during a single-frame colour save) plus `vmmap` to place the addresses. Of the busy thread's samples:

| where | share |
|---|---|
| `/Library/Apple/usr/libexec/oah/libRosettaRuntime` | 66.0% |
| `/usr/libexec/rosetta/runtime` | 29.5% |
| Rosetta JIT (the translated Kodak/TLX code itself) | 4.5% |

`libRosettaRuntime` is stripped, but its strings are Rosetta's x87 library (`x87_fadd_f64`, `x87_fmul_ST`, `x87_fpatan`, `X87State` etc), and the hottest address sits next to the literals `AdditionMultiplication.cpp` / `fma_rs`. My reading is that Kodak's code (VC7.1-era, 2003) does its floating-point maths on the x87 FPU, Apple Silicon has nothing like it, and Rosetta runs each x87 instruction as a call into a software float emulator. Less than 5% of the time is the actual image work.

If you want to reproduce the profile, this is safe to run against a live TLX, unlike `winedbg`, which crashed the client when I attached it:

```
sample $(pgrep -f TLXClientDemo.exe | head -1) 10 1 -mayDie -file ~/Desktop/sample.txt
vmmap $(pgrep -f TLXClientDemo.exe | head -1) > ~/Desktop/vmmap.txt
```

Possible speed improvements

Two projects speed up x87 under Rosetta. I have not tried either yet.

- [athei/x87sidecar](https://github.com/athei/x87sidecar): translates x87 blocks to native ARM code in a separate helper process. Active, no root needed in its Wine mode, and needs the author's patched Wine. I plan to try it on the Mac mini and will report back here.
- [Lifeisawful/rosettax87](https://github.com/Lifeisawful/rosettax87): swaps in faster, less precise x87 handlers. Archived, and needs a helper running as root.

This also ties into the Rosetta point in #3: the colour path depends on Rosetta's x87 support specifically.

Two side findings on #1

- With no DLL overrides, Wine loads its own builtin `msvcr71.dll` and `msvcp71.dll`, not the copies in the app folder (checked with `lsof` on the running client). So the DIFFERENT hashes for those two have no effect at runtime. `mfc71u.dll` does load from the app folder.
- The mismatch comes from the install CD itself. An archive.org image of the official "Pakon 135 v3.0" disc carries both builds: the copies at the installer root (`/` and `fx35install/`) are 7.10.6030, and the ones under `program files/Pakon/` match the manifest exactly. `fetch-oem.sh` sweeps the installer root for DLLs, so it picks up the setup program's copies. Taking the runtimes from `fx35install/program files/Pakon/` instead should make the doctor report all ok (assuming the plonsker archive mirrors the disc, which its layout suggests). All the Kodak binaries on the disc are byte-identical to the manifest.
