"""把 README.md 编译为 res/html/help.html（参考 srw_alpha 的 translate.bat）。

用 pandoc --embed-resources 把 shields 徽章内嵌为 data URI（离线可用），
配合自定义模板（res/html/template.html，仅 $body$）产出纯 body fragment：
不包含 <html>/<head> 包装，也不带 pandoc 默认 CSS——页面样式统一由
help_frame 运行时按明暗主题注入（见 src/ui/help/frame.py 的 setDefaultStyleSheet）。

用法:
    uv run build/make_help.py

依赖:
    - pandoc（PATH 内可执行）
    - 生成徽章内嵌图片时需联网（shields.io），失败仅警告，不影响其余内容
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
README = PROJECT_ROOT / "README.md"
TEMPLATE = PROJECT_ROOT / "res" / "html" / "template.html"
OUT = PROJECT_ROOT / "res" / "html" / "help.html"


def main() -> int:
    cmd = [
        "pandoc",
        "--embed-resources",
        "--no-highlight",  # 去掉 pygments 浅色系高亮内联色，暗色主题下可读
        "--template", str(TEMPLATE),
        str(README),
        "-o", str(OUT),
    ]
    result = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print("pandoc 编译失败", file=sys.stderr)
        return result.returncode

    size = OUT.stat().st_size
    print(f"已生成 {OUT.relative_to(PROJECT_ROOT)} ({size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
