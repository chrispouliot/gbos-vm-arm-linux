{
  description = "gbos-vm on Linux/NixOS (aarch64): build + run Googlebook OS under QEMU/KVM with Venus";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "aarch64-linux" "x86_64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (s: f nixpkgs.legacyPackages.${s});
    in {
      packages = forAll (pkgs: rec {
        # Only the target-side parts of the Android SDK/NDK: the NDK sysroot and clang resource dir
        # (aarch64 Android libs + headers), d8 (a jar) and android.jar. The NDK's own x86_64 host
        # binaries are never used; nixpkgs' clang 19 (the NDK r28 clang is 19 too) drives the
        # sysroot instead, so this works on aarch64-linux.
        gbos-android-sdk = pkgs.stdenvNoCC.mkDerivation {
          pname = "gbos-android-sdk";
          version = "ndk-r28c-bt36.1-api35";
          ndk = pkgs.fetchurl {
            url = "https://dl.google.com/android/repository/android-ndk-r28c-linux.zip";
            sha1 = "a7b54a5de87fecd125a17d54f73c446199e72a64";
          };
          buildTools = pkgs.fetchurl {
            url = "https://dl.google.com/android/repository/build-tools_r36.1_linux.zip";
            sha1 = "936a0d6bd5ae3e2118a7567dddbc95ff67ed46e9";
          };
          platform = pkgs.fetchurl {
            url = "https://dl.google.com/android/repository/platform-35_r02.zip";
            sha1 = "0bb560a90a7a2cbd0dd8348224d518b638fe7949";
          };
          nativeBuildInputs = [ pkgs.unzip ];
          dontUnpack = true;
          dontFixup = true;
          installPhase =
            let
              llvm = pkgs.llvmPackages_19;
              clang = "${llvm.clang-unwrapped}/bin";
            in ''
              runHook preInstall
              tc=$out/ndk/28.2.13676358/toolchains/llvm/prebuilt/linux-x86_64
              mkdir -p $tc/bin tmp
              unzip -q $ndk -d tmp \
                'android-ndk-r28c/toolchains/llvm/prebuilt/linux-x86_64/sysroot/*' \
                'android-ndk-r28c/toolchains/llvm/prebuilt/linux-x86_64/lib/clang/*'
              mv tmp/android-ndk-r28c/toolchains/llvm/prebuilt/linux-x86_64/{sysroot,lib} $tc/
              # Resource dir: headers from the compiler that parses them (arm_neon.h is tied to the
              # exact clang builtins), runtime archives (builtins, libunwind) from the NDK.
              res=$tc/lib/clang-resource
              mkdir -p $res
              ln -s $(echo ${llvm.clang-unwrapped.lib}/lib/clang/*)/include $res/include
              ln -s $(echo $tc/lib/clang/*)/lib $res/lib
              for api in 34 35; do
                for drv in clang clang++; do
                  cat > $tc/bin/aarch64-linux-android$api-$drv <<EOF
              #!${pkgs.runtimeShell}
              # ld.lld via PATH (Android's default linker), not --ld-path: meson's compile-only checks
              # run with -Werror=unused-command-line-argument and would all fail.
              PATH=${llvm.lld}/bin:\$PATH exec ${clang}/$drv --target=aarch64-linux-android$api --sysroot=$tc/sysroot -resource-dir=$res "\$@"
              EOF
                  chmod +x $tc/bin/aarch64-linux-android$api-$drv
                done
              done
              for t in llvm-ar llvm-strip llvm-objcopy llvm-nm llvm-ranlib; do ln -s ${llvm.llvm}/bin/$t $tc/bin/$t; done

              rm -rf tmp && mkdir tmp && unzip -q $buildTools -d tmp
              mkdir -p $out/build-tools && mv tmp/* $out/build-tools/36.1.0
              rm -rf tmp && mkdir tmp && unzip -q $platform -d tmp
              mkdir -p $out/platforms && mv tmp/* $out/platforms/android-35
              patchShebangs $out/build-tools/36.1.0/d8
              runHook postInstall
            '';
        };
        # nixpkgs virglrenderer + the two fixes that let Venus import Android gralloc buffers:
        # GBM-backed (dma-buf exportable) render targets, and host-chosen linear layouts.
        virglrenderer-gbos = pkgs.virglrenderer.overrideAttrs (old: {
          pname = "virglrenderer-gbos";
          postPatch = (old.postPatch or "") + ''
            ${pkgs.buildPackages.python3.interpreter} ${./tools/virgl_venus_share.py} .
            ${pkgs.buildPackages.python3.interpreter} ${./tools/virgl_vkr_linear.py} .
          '';
        });
        # Same plus stderr logging of why vrend resources miss GBM allocation. Swap in with
        # LD_LIBRARY_PATH=$out/lib RENDER_SERVER_EXEC_PATH=$out/libexec/virgl_render_server.
        virglrenderer-debug = virglrenderer-gbos.overrideAttrs (old: {
          pname = "virglrenderer-debug";
          postPatch = old.postPatch + ''
            ${pkgs.buildPackages.python3.interpreter} ${./tools/virgl_gbm_debug.py} .
          '';
        });
        qemu-gbos = pkgs.qemu.override { virglrenderer = virglrenderer-gbos; };
        default = gbos-android-sdk;
      });

      devShells = forAll (pkgs: {
        default = pkgs.mkShellNoCC {
          packages = with pkgs; [
            stdenv.cc gnumake git curl unzip coreutils procps
            (python3.withPackages (ps: [ ps.mako ps.pyyaml ps.packaging ]))
            meson ninja pkg-config bison flex
            erofs-utils e2fsprogs lz4 xdotool
            jdk21_headless
            # nixpkgs QEMU (gtk + sdl + opengl + venus + pipewire) linked to virglrenderer-gbos
            self.packages.${pkgs.stdenv.hostPlatform.system}.qemu-gbos
          ];
          ANDROID_SDK = "${self.packages.${pkgs.stdenv.hostPlatform.system}.gbos-android-sdk}";
          JAVA_HOME = "${pkgs.jdk21_headless.home}";
        };
      });
    };
}
