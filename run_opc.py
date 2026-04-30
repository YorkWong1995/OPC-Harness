"""OPC 运行脚本"""
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from opc.cli import main

if __name__ == "__main__":
    main()
