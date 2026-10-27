"""Тесты модуля токенизации кода (Мельниченко В. С.)."""
from antiplagiat import tokens

ORIG = '''def total(arr):
    s = 0
    for x in arr:
        s += x
    return s

def biggest(arr):
    m = arr[0]
    for x in arr:
        if x > m:
            m = x
    return m
'''
# переименование переменных и перестановка функций
COPY = '''def maximum(values):
    best = values[0]
    for v in values:
        if v > best:
            best = v
    return best

def summa(values):
    acc = 0
    for v in values:
        acc += v
    return acc
'''

def test_tokens_rename_does_not_hide_copy():
    a = tokens.tokenize_file(ORIG, "python", "a.py")
    b = tokens.tokenize_file(COPY, "python", "b.py")
    assert tokens.compare(a, b, k=4, window=2)["similarity"] >= 0.8

def test_comments_removed():
    t = tokens.tokenize_file("int a = 1; // comment\n/* block */ int b = 2;", "cpp", "x.cpp")
    assert [x.kind for x in t] == ["int", "ID", "=", "NUM", ";", "int", "ID", "=", "NUM", ";"]
