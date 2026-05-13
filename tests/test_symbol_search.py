"""测试代码符号搜索"""

from pathlib import Path

from src.opc.knowledge.symbol_search import SymbolIndex


def test_index_python_file(tmp_path):
    """测试解析 Python 文件提取符号"""
    code = '''
class MyClass:
    def method_one(self, x: int) -> str:
        pass

def standalone_function(a, b):
    return a + b

async def async_handler(request):
    pass
'''
    py_file = tmp_path / "example.py"
    py_file.write_text(code, encoding="utf-8")

    idx = SymbolIndex()
    symbols = idx.index_file(py_file)

    names = [s.name for s in symbols]
    assert "MyClass" in names
    assert "method_one" in names
    assert "standalone_function" in names
    assert "async_handler" in names

    # 验证类型
    class_sym = next(s for s in symbols if s.name == "MyClass")
    assert class_sym.kind == "class"

    func_sym = next(s for s in symbols if s.name == "standalone_function")
    assert func_sym.kind == "function"

    async_sym = next(s for s in symbols if s.name == "async_handler")
    assert async_sym.kind == "function"
    assert "async def" in async_sym.signature


def test_search_symbols(tmp_path):
    """测试符号搜索"""
    code = '''
def get_user():
    pass

def get_user_by_id(user_id):
    pass

def delete_user():
    pass

class UserService:
    pass
'''
    py_file = tmp_path / "users.py"
    py_file.write_text(code, encoding="utf-8")

    idx = SymbolIndex()
    idx.index_file(py_file)

    results = idx.search("get_user")
    assert len(results) >= 2
    assert results[0].name == "get_user"  # exact match first

    results = idx.search("User", kind="class")
    assert len(results) == 1
    assert results[0].name == "UserService"


def test_index_directory(tmp_path):
    """测试目录索引"""
    (tmp_path / "a.py").write_text("def foo(): pass\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("class Bar: pass\n", encoding="utf-8")
    (tmp_path / "not_python.txt").write_text("hello", encoding="utf-8")

    idx = SymbolIndex()
    count = idx.index_directory(tmp_path)
    assert count == 2


def test_syntax_error_file(tmp_path):
    """语法错误文件不崩溃"""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def broken(:\n", encoding="utf-8")

    idx = SymbolIndex()
    symbols = idx.index_file(bad_file)
    assert symbols == []
