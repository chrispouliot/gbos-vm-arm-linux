# gbos-vm-arm-linux

A fork of [skylartaylor/gbos-vm](https://github.com/skylartaylor/gbos-vm) that runs the Googlebook OS VM on an
aarch64 Linux host with KVM, built and run from NixOS. Tested on an Asus Zenbook A14 (Snapdragon X2 Elite,
Adreno X2-90, turnip). Everything about the image itself (what is downloaded, how the vendor partition is rebuilt,
the security caveats) is unchanged; read the upstream README for that.

## What this fork changes

- **`flake.nix`**: a dev shell with everything the build and the VM need (QEMU with virglrenderer/Venus, GTK/SDL GL
  and PipeWire, meson, erofs-utils, e2fsprogs, lz4, JDK, xdotool), and `gbos-android-sdk`: the NDK r28c sysroot,
  d8 and `android.jar`, driven by nixpkgs' clang 19, so the guest pieces cross-build on aarch64-linux (the NDK has no
  aarch64 host tools).
- **Build scripts**: Linux branches instead of Homebrew/UTM/`hdiutil`; `sha256sum`, reflink copies, `SOURCE_DATE_EPOCH`
  unset for the vendor rebuild; `patches/mesa-android-mapper5.patch` fixed to apply with GNU `patch`. No Mac host
  pieces are built: stock QEMU + virglrenderer do the GPU path with real dma-bufs.
- **`run/run_vm.py`, `run/launch.py`**: QEMU with KVM (TCG fallback), guest RAM in a shared memfd, `virtio-gpu-gl`
  with Venus, QEMU's own GTK or SDL GL window instead of the Cocoa viewer, PipeWire audio, and the launch options
  below.
- **Two images.** The default is GLES-only: SurfaceFlinger, HWUI and Chrome render through virgl. `GBOS_VULKAN=1`
  builds a Venus image with SurfaceFlinger/HWUI/Chrome on Vulkan.
- **`virglrenderer-gbos`** (`tools/virgl_venus_share.py`, `tools/virgl_vkr_linear.py`): the dev shell's QEMU links a
  patched virglrenderer that makes Android gralloc buffers shareable with Venus on a Linux host: render targets are
  allocated through GBM so they export as dma-bufs, and linear imports use the host driver's own layout.
  `virglrenderer-debug` adds logging (`tools/virgl_gbm_debug.py`).

## Build

Needs an aarch64 Linux host with a usable `/dev/kvm`, Nix with flakes, and about 60 GB free (110 GB on filesystems
without reflinks, such as ext4).

```sh
nix develop
./install.sh                                                     # GLES image in work/image
GBOS_VULKAN=1 GBOS_IMAGE_DIR=$PWD/work/image-vk ./build-image.sh # optional Vulkan image
```

## Launch options

```sh
python3 run/launch.py work [options]
```

| Option | Default | |
|---|---|---|
| `--display WxH` | `1920x1200` | Guest resolution. |
| `--window WxH` | `--display` | Window size in X11 pixels (physical pixels with `xwayland-native-scaling`, logical without); the guest is scaled to fit. Match `--display` for 1:1 pixels. |
| `--density DPI` | `240 × width / 1920` | Android display density. 160 × your GNOME scale matches the host UI size (150% → 240). |
| `--fullscreen` | off | Start full screen. Ctrl+Alt+F toggles. |
| `--memory MIB` | `4096` | Guest RAM. |
| `--cpus N` | `6` | vCPUs. |
| `--image DIR` | `work/image` | Image folder, e.g. `work/image-vk`. |
| `--vulkan` | off | Required for an image built with `GBOS_VULKAN=1`. |
| `--ui gtk\|sdl` | `gtk` | QEMU window. GTK runs through XWayland so the mouse grab works under Wayland. |
| `--offline` | off | No network. |
| `--no-audio` | off | No audio device. |

Examples, for a 4K panel at 150%:

```sh
python3 run/launch.py work --display 3840x2160 --density 240 --fullscreen --image work/image-vk --vulkan
python3 run/launch.py work --display 2880x1620 --density 240 --image work/image-vk --vulkan
```

Click the window to capture the mouse; Ctrl+Alt+G (GTK) or Ctrl+Alt (SDL) releases it. Closing the window is disabled
so it cannot cut power to Android: shut down from Android or with Ctrl+C in the terminal. If Android starts treating
every key as a shortcut, a modifier is stuck: press and release Super, Ctrl, Alt and Shift inside the VM.

## License

MIT, as upstream; `patches/cocoaspice-viewer.patch` stays Apache-2.0.
