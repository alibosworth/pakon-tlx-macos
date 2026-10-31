# Agent notes

## First order of business

Read `docs/notes-slow-colour-saves.md` before anything else. It holds the open
investigation into slow colour-processed TIFF saves (~26 s per frame), what has
been ruled out, the next steps, and how Wine is set up on this machine
(launch with `PAKON_WINE` pointing at Wine 11 in `~/Applications`).

Do not attach `winedbg` to a running TLXClientDemo: it crashes the client.
macOS `sample <pid> 10 1 -mayDie -file out.txt` plus `vmmap <pid>` is safe
(used during a save on 31 Oct) and is the way to profile it.
