#!/bin/bash
# Build everything from source and leave a runnable Googlebook VM in $GOOGLEBOOK_WORK (default ./work).
# Run:  ./install.sh     then:  python3 run/launch.py work
. "$(dirname "$0")/lib.sh"
[ "$(uname -m)" = arm64 ] || die "Apple Silicon Mac required"
mkdir -p "$WORK"
free_gb=$(( $(df -k "$WORK" | tail -1 | awk '{print $4}') / 1048576 ))
[ "$free_gb" -ge 60 ] || die "only ${free_gb} GB free where $WORK lives; this needs about 60 GB (downloads, the unpacked image, and room for the VM to grow)"
ram_gb=$(( $(sysctl -n hw.memsize) / 1073741824 ))
[ "$ram_gb" -ge 16 ] || echo "warning: ${ram_gb} GB RAM. The VM takes 4 GB and the builds want a few more; close other apps first."
"$ROOT/fetch.sh"
"$ROOT/build-host.sh"
"$ROOT/build-guest.sh"
"$ROOT/build-image.sh"
say "Done. Open \"$WORK/host/Googlebook VM.app\" (drag it to your Dock if you like)."
