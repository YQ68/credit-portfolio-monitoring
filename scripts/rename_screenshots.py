# -*- coding: utf-8 -*-
"""Đổi tên ảnh chụp báo cáo Power BI về tên ASCII cố định.

Lệnh `powerbi-desktop screenshot-all` luôn đặt tên ảnh theo tên trang hiển thị
(ví dụ "1. Tổng quan.png"), nên mỗi lần chụp lại sẽ ra tên có dấu và dấu cách.
Script này ghép ảnh theo số thứ tự trang ở đầu tên file rồi đổi sang bốn tên
cố định: 01-tong-quan.png, 02-kenh-ban.png, 03-vintage.png, 04-thu-hoi.png.
Ảnh cũ cùng tên bị ghi đè. Chạy nhiều lần không lỗi: file đã mang tên ASCII
thì bỏ qua, thư mục không có ảnh nào cần đổi thì chỉ báo và thoát.

Chạy: python scripts/rename_screenshots.py [thư_mục_ảnh]
Mặc định thư mục ảnh là docs/screenshots.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "docs" / "screenshots"

# Số thứ tự trang -> tên file ASCII cố định.
TARGETS = {
    1: "01-tong-quan.png",
    2: "02-kenh-ban.png",
    3: "03-vintage.png",
    4: "04-thu-hoi.png",
}

# Tên do CLI đặt bắt đầu bằng "<số>." rồi dấu cách, ví dụ "2. Kênh bán.png".
RAW_NAME = re.compile(r"^(\d+)\.\s+.+\.png$", re.IGNORECASE)


def main(folder: Path) -> int:
    if not folder.is_dir():
        print(f"Không tìm thấy thư mục: {folder}")
        return 1

    renamed = 0
    for src in sorted(folder.iterdir()):
        match = RAW_NAME.match(src.name)
        if not match:
            continue  # đã là tên ASCII hoặc file khác, bỏ qua
        target = TARGETS.get(int(match.group(1)))
        if target is None:
            print(f"Bỏ qua {src.name}: không có trang số {match.group(1)} trong bảng tên")
            continue
        src.replace(folder / target)  # ghi đè nếu đã có
        print(f"{src.name} -> {target}")
        renamed += 1

    if renamed == 0:
        print("Không có ảnh nào cần đổi tên.")
    missing = [name for name in TARGETS.values() if not (folder / name).exists()]
    if missing:
        print("Còn thiếu: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    folder_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    sys.exit(main(folder_arg))
