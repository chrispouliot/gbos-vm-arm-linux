#!/bin/bash
# Build everything from source and leave a runnable Googlebook VM in $GOOGLEBOOK_WORK (default ./work).
# Run:  ./install.sh     then:  python3 run/launch.py work
. "$(dirname "$0")/lib.sh"
case "$(uname -s)/$(uname -m)" in
  Darwin/arm64|Linux/aarch64) ;;
  *) die "needs an Apple Silicon Mac or an aarch64 Linux host (the guest is ARM64)" ;;
esac
mkdir -p "$WORK"
free_gb=$(( $(df -k "$WORK" | tail -1 | awk '{print $4}') / 1048576 ))
need_gb=60
# The image steps copy a 19 GB disk three times; only APFS/btrfs/XFS make those copies free.
[ "$IS_MAC" = 1 ] || case "$(stat -f -c %T "$WORK")" in btrfs|xfs) ;; *) need_gb=110 ;; esac
[ "$free_gb" -ge "$need_gb" ] || die "only ${free_gb} GB free where $WORK lives; this needs about ${need_gb} GB (downloads, the unpacked image, and room for the VM to grow)"
if [ "$IS_MAC" = 1 ]; then ram_gb=$(( $(sysctl -n hw.memsize) / 1073741824 ))
else ram_gb=$(( $(awk '/^MemTotal:/{print $2}' /proc/meminfo) / 1048576 )); fi
[ "$ram_gb" -ge 16 ] || echo "warning: ${ram_gb} GB RAM. The VM takes 4 GB and the builds want a few more; close other apps first."
"$ROOT/fetch.sh"
"$ROOT/build-host.sh"
"$ROOT/build-guest.sh"
"$ROOT/build-image.sh"
if [ "$IS_MAC" = 1 ]; then say "Done. Open \"$WORK/host/Googlebook VM.app\" (drag it to your Dock if you like)."
else say "Done. Run: python3 run/launch.py $WORK"; fi
