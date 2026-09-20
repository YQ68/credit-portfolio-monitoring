"""Tải dữ liệu Home Credit Default Risk từ Kaggle và giải nén vào data/raw/.

Chuẩn bị một lần:
1. Đăng nhập Kaggle, mở https://www.kaggle.com/competitions/home-credit-default-risk/rules
   và chấp nhận luật của competition (bỏ qua bước này sẽ bị lỗi 403).
2. Xác thực Kaggle CLI: chạy `kaggle auth login` (đăng nhập qua trình duyệt).
   Cách khác: tạo token tại https://www.kaggle.com/settings/api rồi đặt vào biến môi trường
   KAGGLE_API_TOKEN hoặc lưu vào file %USERPROFILE%\\.kaggle\\access_token.

Tải tay: tải file zip ở tab Data của competition, giải nén các file CSV vào data/raw/.
"""
import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from load_raw import DEFAULT_RAW_DIR, RAW_FILES

COMPETITION = "home-credit-default-risk"
EXTRA_FILES = ["HomeCredit_columns_description.csv"]  # mô tả cột chính thức


def find_kaggle_cli():
    found = shutil.which("kaggle")
    if found:
        return found
    # Khi chưa activate venv, CLI nằm cạnh python.exe
    local = Path(sys.executable).parent / ("kaggle.exe" if sys.platform == "win32" else "kaggle")
    return str(local) if local.exists() else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Download Home Credit data from Kaggle.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    args = parser.parse_args()

    kaggle = find_kaggle_cli()
    if kaggle is None:
        sys.exit("Kaggle CLI not found. Run: pip install -r requirements.txt")

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = args.raw_dir / f"{COMPETITION}.zip"
    if not zip_path.exists():
        command = [kaggle, "competitions", "download", "-c", COMPETITION, "-p", str(args.raw_dir)]
        # Kaggle CLI in ra đường dẫn tải về. Nếu đường dẫn có dấu tiếng Việt và console
        # dùng bảng mã cũ (cp1252), CLI sẽ lỗi khi in. Ép tiến trình con dùng UTF-8.
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        try:
            subprocess.run(command, check=True, env=env)
        except subprocess.CalledProcessError:
            sys.exit("Download failed. Run `kaggle auth login` and make sure you accepted the competition rules.")

    wanted = set(RAW_FILES.values()) | set(EXTRA_FILES)
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if name in wanted:
                print(f"  extracting {name}")
                archive.extract(name, args.raw_dir)

    missing = sorted(wanted - {p.name for p in args.raw_dir.iterdir()})
    if missing:
        sys.exit(f"Not found in zip: {', '.join(missing)}")
    print(f"Done. {zip_path.name} can be deleted to free disk space.")


if __name__ == "__main__":
    main()
