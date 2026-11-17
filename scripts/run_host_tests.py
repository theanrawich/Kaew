"""Cross-platform C++ host tests; no boards, secrets or pump GPIO are used."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TESTS = ("safety", "scale", "protocol", "integration", "dispense", "durable_queue", "audio", "gateway_dispensing")


def run(command):
    subprocess.run([str(arg) for arg in command], check=True, cwd=ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="g++")
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if not compiler:
        parser.error(f"compiler unavailable: {args.compiler}")
    run([compiler, "--version"])
    with tempfile.TemporaryDirectory(prefix="kaew-host-") as directory:
        work = Path(directory)
        for name in TESTS:
            executable = work / f"{name}.exe"
            # Keep original programs' compiler policy; enforce warnings on the
            # new integration suite without changing unrelated legacy modules.
            warnings = ["-Wall", "-Wextra", "-Werror"] if name == "gateway_dispensing" else []
            run([compiler, "-std=c++17", *warnings, "-Ifirmware/include",
                 ROOT / "firmware/test" / f"{name}_test.cpp", "-o", executable])
            run([executable])
            print(f"PASS host/{name}", flush=True)
        # Isolate header from ANY private cloud_config.local.h in the checkout.
        shutil.copyfile(ROOT / "firmware/include/cloud_config.h", work / "cloud_config.h")
        for mode in ("empty", "url_only", "token_only", "configured", "forced_off", "forced_on"):
            url = '#define KAEW_CLOUD_URL "https://example.invalid/api/telemetry"\n'
            token = '#define KAEW_CLOUD_TOKEN "test-only-placeholder"\n'
            local = work / "cloud_config.local.h"
            local.write_text({"empty": "", "url_only": url, "token_only": token,
                              "configured": url + token, "forced_off": url + token + '#define KAEW_CLOUD_ENABLED 0\n',
                              "forced_on": ""}[mode], encoding="utf-8")
            extra = []
            if mode == "forced_on":
                local.unlink()
                extra = ["-DKAEW_CLOUD_ENABLED=1"]
            expected = int(mode in ("configured", "forced_on"))
            executable = work / "cloud_config.exe"
            run([compiler, "-std=c++17", f"-I{work}", f"-DEXPECT_ENABLED={expected}", *extra,
                 ROOT / "firmware/test/cloud_config_test.cpp", "-o", executable])
            run([executable])
            print(f"PASS cloud-config/{mode}", flush=True)
    print("PASS: 8 host programs (25 gateway scenarios), 6 cloud configuration cases", flush=True)


if __name__ == "__main__":
    main()
