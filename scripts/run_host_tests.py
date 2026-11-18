"""Cross-platform C++ host tests; no boards, secrets or pump GPIO are used."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TESTS = ("safety", "scale", "protocol", "integration", "dispense", "durable_queue", "audio", "gateway_dispensing", "ai_refill", "drink_detection")


def run(command):
    subprocess.run([str(arg) for arg in command], check=True, cwd=ROOT)


def check_pump_pin_guards(compiler, work):
    # These stubs provide compile syntax only, never hardware or SoC validation.
    # Compile the ACTUAL pump_gpio.h with commissioning enabled in inert host
    # fixtures; never produce/flash an enabled ESP32 image or execute the fixture.
    (work / "Arduino.h").write_text(
        "#pragma once\n#define INPUT 0\n#define OUTPUT 1\n"
        "inline void digitalWrite(int, int) {}\ninline void pinMode(int, int) {}\n"
        "inline int digitalRead(int) { return 0; }\n", encoding="utf-8")
    (work / "driver").mkdir()
    (work / "driver/gpio.h").write_text(
        "#pragma once\n#define GPIO_IS_VALID_GPIO(pin) ((pin) >= 0 && (pin) < 49)\n"
        "#define GPIO_IS_VALID_OUTPUT_GPIO(pin) GPIO_IS_VALID_GPIO(pin)\n", encoding="utf-8")
    commissioned = ["-DKAEW_PUMP_COMMISSIONED=1", "-DKAEW_INDEPENDENT_CUTOFF_VERIFIED=1",
                    "-DKAEW_PUMP_ON_LEVEL=1", "-DKAEW_ESTOP_SAFE_LEVEL=1"]
    cases = [("default-disabled", [], False),
             ("non-console-positive-control", [*commissioned, "-DKAEW_PUMP_PIN=15", "-DKAEW_ESTOP_PIN=16"], False)]
    for pin in (43, 44):
        cases.append((f"reject-pump-{pin}", [*commissioned, f"-DKAEW_PUMP_PIN={pin}", "-DKAEW_ESTOP_PIN=16"], True))
        cases.append((f"reject-estop-{pin}", [*commissioned, "-DKAEW_PUMP_PIN=15", f"-DKAEW_ESTOP_PIN={pin}"], True))
    for name, flags, must_fail in cases:
        command = [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", f"-I{work}", "-Ifirmware/include", *flags,
                   "-c", str(ROOT / "firmware/test/pump_gpio_compile_test.cpp"), "-o", str(work / f"pump_gpio_{name}.o")]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if must_fail:
            if result.returncode == 0 or "GPIO conflicts with peripherals, UART0 console" not in result.stderr:
                raise RuntimeError(f"{name}: expected reserved-pin assertion, got:\n{result.stdout}{result.stderr}")
        elif result.returncode:
            raise RuntimeError(f"{name}: positive control failed:\n{result.stdout}{result.stderr}")
        print(f"PASS pump-gpio/{name}" + (" (expected compile failure)" if must_fail else ""), flush=True)


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
        check_pump_pin_guards(compiler, work)
        for name in TESTS:
            executable = work / f"{name}.exe"
            # Keep original programs' compiler policy; enforce warnings on the
            # new integration suite without changing unrelated legacy modules.
            warnings = ["-Wall", "-Wextra", "-Werror"] if name in ("gateway_dispensing", "ai_refill", "drink_detection") else []
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
            # Avoid overwriting a just-run executable still held by Windows/AV.
            executable = work / f"cloud_config_{mode}.exe"
            run([compiler, "-std=c++17", f"-I{work}", f"-DEXPECT_ENABLED={expected}", *extra,
                 ROOT / "firmware/test/cloud_config_test.cpp", "-o", executable])
            run([executable])
            print(f"PASS cloud-config/{mode}", flush=True)
    print(f"PASS: {len(TESTS)} host programs (25 gateway + 12 AI scenarios), 6 pump GPIO compile cases, 6 cloud configuration cases", flush=True)


if __name__ == "__main__":
    main()
