"""Automatic Joern installation and management for KnowGraph.

This module handles downloading, installing, and verifying the Joern CLI.
"""

import logging
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

# Import setuptools locally to avoid import errors if not installed
try:
    from setuptools.command.install import install  # type: ignore
except ImportError:
    install = object  # type: ignore

logger = logging.getLogger(__name__)

# Joern configuration
JOERN_VERSION = "4.0.457"
JOERN_REPO = "joernio/joern"
INSTALL_DIR = Path.home() / ".knowgraph" / "joern"


def check_jdk() -> bool:
    """Check if JDK 11+ is installed.

    Returns
    -------
        True if JDK is available, False otherwise

    """
    try:
        result = subprocess.run(
            ["java", "-version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Parse version from output (format: "java version "11.0.x" ...")
        # Note: java -version outputs to stderr
        version_output = result.stderr
        if not version_output and result.stdout:
            version_output = result.stdout

        version_line = version_output.split("\n")[0]
        if "version" in version_line:
            version_str = version_line.split('"')[1]
            try:
                major_version = int(version_str.split(".")[0])
                # Handle "1.8.0" style (Java 8) where first part is 1
                if major_version == 1:
                    major_version = int(version_str.split(".")[1])

                if major_version >= 11:
                    logger.info(f"✅ JDK {version_str} detected")
                    return True
            except (ValueError, IndexError):
                # Fallback for non-standard version strings
                pass

        # If we got here but command succeeded, it might be a valid java but parsing failed
        # Just return True if we can't parse but it ran? No, safer to be strict or improve parsing.
        # Strict for now.
        return False
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError, ValueError, subprocess.TimeoutExpired):
        return False


def check_coreutils() -> bool:
    """Check if GNU coreutils (greadlink) is installed on macOS.

    Returns
    -------
        True if coreutils is available or not on macOS, False if on macOS without coreutils

    """
    # Only required on macOS
    if platform.system() != "Darwin":
        return True

    try:
        subprocess.run(
            ["greadlink", "--version"],
            check=True,
            capture_output=True,
            timeout=5,
        )
        logger.info("✅ GNU coreutils (greadlink) detected")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def download_joern(version: str = JOERN_VERSION) -> Path:
    """Download Joern CLI from GitHub releases.

    Args:
    ----
        version: Joern version to download

    Returns:
    -------
        Path to downloaded zip file

    """
    system = platform.system().lower()

    # Construct download URL
    filename = "joern-cli.zip"

    url = f"https://github.com/{JOERN_REPO}/releases/download/v{version}/{filename}"

    # Create temp directory
    temp_dir = Path.home() / ".knowgraph" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    zip_path = temp_dir / filename

    # Skip download if file already exists and is valid
    if zip_path.exists():
        # Verify the zip file is valid
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                # Try to read the file list to verify it's a valid zip
                zip_ref.namelist()
            logger.info(f"✅ Found valid existing download at {zip_path}")
            print("✅ Using existing Joern download...")
            return zip_path
        except zipfile.BadZipFile:
            logger.warning("⚠️  Existing zip file is corrupted, will re-download")
            print("⚠️  Existing download is corrupted, re-downloading...")
            zip_path.unlink()  # Delete corrupted file

    logger.info(f"📥 Downloading Joern {version} from {url}")
    print(f"📥 Downloading Joern {version}...")

    try:
        urlretrieve(url, zip_path)
        logger.info(f"✅ Downloaded to {zip_path}")
        return zip_path
    except Exception as e:
        logger.error(f"❌ Download failed: {e}")
        raise


def extract_joern(zip_path: Path, install_dir: Path) -> bool:
    """Extract Joern CLI to installation directory.

    Args:
    ----
        zip_path: Path to downloaded zip file
        install_dir: Target installation directory

    Returns:
    -------
        True if extraction successful

    """
    try:
        logger.info(f"📦 Extracting Joern to {install_dir}")
        print("📦 Extracting Joern...")

        # Remove old installation if exists
        if install_dir.exists():
            shutil.rmtree(install_dir)

        install_dir.mkdir(parents=True, exist_ok=True)

        # Extract zip
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(install_dir)

        # Make executables executable on Unix
        if platform.system() != "Windows":
            joern_cli_dir = install_dir / "joern-cli"
            if joern_cli_dir.exists():
                # Make main Joern executables executable
                for exe in ["joern", "joern-parse", "joern-export", "c2cpg.sh",
                           "csharpsrc2cpg", "ghidra2cpg", "gosrc2cpg", "javasrc2cpg",
                           "jimple2cpg", "jssrc2cpg", "kotlin2cpg", "php2cpg",
                           "pysrc2cpg", "rubysrc2cpg", "swiftsrc2cpg", "x2cpg"]:
                    exe_path = joern_cli_dir / exe
                    if exe_path.exists():
                        exe_path.chmod(0o755)

                # Make all files in ANY bin/ directory executable (including frontends)
                # This covers joern-cli/bin/ and joern-cli/frontends/*/bin/
                for bin_file in joern_cli_dir.rglob("bin/*"):
                    if bin_file.is_file():
                        bin_file.chmod(0o755)

        logger.info("✅ Extraction complete")
        return True

    except Exception as e:
        logger.error(f"❌ Extraction failed: {e}")
        return False


def verify_installation() -> bool:
    """Verify Joern installation by checking executable and directory structure.

    Returns
    -------
        True if Joern is properly installed

    """
    joern_cli_dir = INSTALL_DIR / "joern-cli"
    joern_exe = "joern.bat" if platform.system() == "Windows" else "joern"
    joern_path = joern_cli_dir / joern_exe

    # Check if executable exists
    if not joern_path.exists():
        logger.error(f"❌ Joern executable not found at {joern_path}")
        return False

    # Check if bin directory exists (required by joern script)
    bin_dir = joern_cli_dir / "bin"
    if not bin_dir.exists():
        logger.error(f"❌ Joern bin directory not found at {bin_dir}")
        return False

    # On macOS, verify coreutils is available
    if platform.system() == "Darwin":
        if not check_coreutils():
            logger.error("❌ GNU coreutils not found - required on macOS")
            return False

    # Try to run joern-parse --help (non-interactive, returns immediately)
    try:
        joern_parse = joern_cli_dir / ("joern-parse.bat" if platform.system() == "Windows" else "joern-parse")
        result = subprocess.run(
            [str(joern_parse), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(joern_cli_dir),  # Run from joern-cli directory
        )

        # Check both stdout and stderr as joern may output to either
        output = result.stdout + result.stderr
        if "usage" in output.lower() or "joern" in output.lower() or result.returncode == 0:
            logger.info("✅ Joern installation verified")
            return True
        else:
            logger.error(f"❌ Joern verification failed: {output}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("❌ Joern verification timed out")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to verify Joern: {e}")
        return False


def install_joern() -> bool:
    """Main installation function.

    Returns
    -------
        True if installation successful

    """
    print("\n" + "="*60)
    print("🧠 KnowGraph - Joern Integration Setup")
    print("="*60 + "\n")

    # Step 0: Check if already installed
    print("🔍 Checking for existing Joern installation...")
    if verify_installation():
        print("\n✅ Joern is already installed and verified!")
        print(f"   Location: {INSTALL_DIR / 'joern-cli'}")
        print("   Joern features are available.")
        print("\n" + "="*60 + "\n")
        return True

    # Step 1: Check JDK
    print("🔍 Checking for JDK...")
    if not check_jdk():
        print("\n⚠️  WARNING: JDK 11+ not found!")
        print("   Joern features will be disabled.")
        print("   To enable advanced code analysis:")
        print("   1. Install JDK 11 or higher")
        print("   2. Run: pip install --force-reinstall knowgraph")
        print("\n" + "="*60 + "\n")
        return False

    # Step 1.5: Check coreutils on macOS
    if platform.system() == "Darwin":
        print("🔍 Checking for GNU coreutils (macOS)...")
        if not check_coreutils():
            print("\n⚠️  WARNING: GNU coreutils not found!")
            print("   Joern requires 'greadlink' which is part of GNU coreutils.")
            print("   To install:")
            print("   brew install coreutils")
            print("\n   After installing, re-run this script.")
            print("\n" + "="*60 + "\n")
            return False

    # Step 2: Download Joern
    try:
        zip_path = download_joern()
    except Exception as e:
        print(f"\n❌ Failed to download Joern: {e}")
        print("   Joern features will be disabled.")
        print("   You can manually install Joern later.")
        return False

    # Step 3: Extract
    if not extract_joern(zip_path, INSTALL_DIR):
        print("\n❌ Failed to extract Joern")
        print("   Joern features will be disabled.")
        return False

    # Step 4: Verify
    if not verify_installation():
        print("\n❌ Joern installation verification failed")
        print("   Joern features will be disabled.")
        return False

    # Step 5: Cleanup
    try:
        zip_path.unlink()
    except Exception:
        pass

    print("\n✅ Joern installed successfully!")
    print(f"   Location: {INSTALL_DIR / 'joern-cli'}")
    print("   Joern features are now available.")
    print("\n" + "="*60 + "\n")
    return True


class PostInstallCommand(install):
    """Setuptools command to run Joern installation after pip install."""

    def run(self):
        """Execute post-install Joern setup."""
        # First run the standard install
        if install != object:
            install.run(self)

        # Then run Joern setup
        try:
            install_joern()
        except Exception as e:
            logger.warning(f"Joern installation failed: {e}")
            print("\n⚠️  Joern installation encountered issues.")
            print("   KnowGraph will work without Joern, but advanced features will be limited.")
            print("   You can retry with: knowgraph-setup-joern")


if __name__ == "__main__":
    # Enable logging for standalone execution
    logging.basicConfig(level=logging.INFO)

    success = install_joern()
    sys.exit(0 if success else 1)
