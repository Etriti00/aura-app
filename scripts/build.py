#!/usr/bin/env python3
"""Cross-platform build script for Aura."""
import sys
import subprocess
import platform
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    print(f"Building Aura for {platform.system()} ({platform.machine()})...")

    # Generate macOS icon if needed
    if sys.platform == "darwin":
        icns_path = os.path.join(PROJECT_ROOT, "assets", "icons", "aura_icon.icns")
        if not os.path.exists(icns_path):
            print("Generating macOS icon...")
            script = os.path.join(PROJECT_ROOT, "scripts", "build_icns.sh")
            subprocess.run(["bash", script], check=True)

    # Install playwright browsers
    print("Installing Playwright Chromium...")
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
    )

    # Run PyInstaller
    print("Running PyInstaller...")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "aura.spec", "--noconfirm"],
        cwd=PROJECT_ROOT,
        check=True,
    )

    if sys.platform == "darwin":
        print("\nBuild complete: dist/Aura.app")
        print("To create a DMG: hdiutil create -volname Aura -srcfolder dist/Aura.app -ov Aura.dmg")
    elif sys.platform == "win32":
        print("\nBuild complete: dist/Aura/Aura.exe")
    else:
        print("\nBuild complete: dist/Aura/Aura")
        print("Run scripts/linux/install.sh to install system-wide.")


if __name__ == "__main__":
    main()
