"""Модуль 2. Лексический анализ и токенизация кода.
Ответственный: Мельниченко В. С.

Что делает модуль:
  1. удаляет комментарии и пустые строки;
  2. разбивает код на токены (Python, C++, Java);
  3. нормализует идентификаторы, числа и строки (ID, NUM, STR), поэтому
     переименование переменных не скрывает совпадение;
  4. сравнивает цепочки токенов методом отпечатков (k-граммы + winnowing)
     и возвращает процент сходства и номера совпавших строк.
"""
from __future__ import annotations
import io, re, keyword, tokenize
from dataclasses import dataclass
import hashlib

@dataclass(frozen=True)
class Tok:
    kind: str      # нормализованное значение: ключевое слово, оператор, ID, NUM, STR
    file: str
    line: int

CPP_KW = set("""alignas alignof and asm auto bool break case catch char class const constexpr const_cast continue
decltype default delete do double dynamic_cast else enum explicit export extern false float for friend goto if inline
int long mutable namespace new noexcept not nullptr operator or private protected public register reinterpret_cast
return short signed sizeof static static_assert static_cast struct switch template this throw true try typedef typeid
typename union unsigned using virtual void volatile while include define std cout cin endl vector string""".split())
JAVA_KW = set("""abstract assert boolean break byte case catch char class const continue default do double else enum
extends final finally float for goto if implements import instanceof int interface long native new package private
protected public return short static strictfp super switch synchronized this throw throws transient try void volatile
while true false null var String System out println print Scanner""".split())

_C_RE = re.compile(r"""
  (?P<comment>//[^\n]*|/\*.*?\*/)
| (?P<pre>\#[^\n]*)
| (?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
| (?P<num>\b\d[\d.xXa-fA-F]*[uUlLfF]*\b)
| (?P<id>[A-Za-z_]\w*)
| (?P<op>::|->|\+\+|--|<<=|>>=|\+=|-=|\*=|/=|%=|&=|\|=|\^=|<=|>=|==|!=|&&|\|\||<<|>>|[-+*/%=&|^!~<>?:;,.(){}\[\]])
| (?P<nl>\n)
| (?P<ws>[ \t\r\f]+)
| (?P<other>.)
""", re.S | re.X)

def _tokens_c_like(src: str, path: str, kw: set[str]) -> list[Tok]:
    out, line = [], 1
    for m in _C_RE.finditer(src):
        g, s = m.lastgroup, m.group()
        if g in ("comment", "pre"):
            line += s.count("\n"); continue          # комментарии и #include удаляем
        if g == "nl":
            line += 1; continue
        if g in ("ws", "other"):
            continue
        if g == "str":   val = "STR"
        elif g == "num": val = "NUM"
        elif g == "id":  val = s if s in kw else "ID"
        else:            val = s
        out.append(Tok(val, path, line))
    return out

def _tokens_python(src: str, path: str) -> list[Tok]:
    out = []
    skip = {tokenize.COMMENT, tokenize.NL, tokenize.ENCODING, tokenize.ENDMARKER}
    try:
        for t in tokenize.generate_tokens(io.StringIO(src).readline):
            if t.type in skip:
                continue
            if t.type == tokenize.NAME:
                val = t.string if (keyword.iskeyword(t.string) or t.string in ("print", "range", "len", "input")) else "ID"
            elif t.type == tokenize.NUMBER: val = "NUM"
            elif t.type == tokenize.STRING: val = "STR"
            elif t.type == tokenize.NEWLINE: val = ";"
            elif t.type == tokenize.INDENT: val = "{"
            elif t.type == tokenize.DEDENT: val = "}"
            else: val = t.string
            out.append(Tok(val, path, t.start[0]))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # синтаксически битый файл: падаем обратно на C-подобный разбор
        out = _tokens_c_like(re.sub(r"#[^\n]*", "", src), path, set(keyword.kwlist))
    # докстринги не учитываем: строка-выражение сразу после ';' / '{'
    clean, skip_next = [], False
    for i, t in enumerate(out):
        if skip_next:
            skip_next = False; continue
        if t.kind == "STR" and (i == 0 or out[i-1].kind in (";", "{", ":")) and i + 1 < len(out) and out[i+1].kind == ";":
            skip_next = True; continue
        clean.append(t)
    return clean

def tokenize_file(text: str, lang: str, path: str) -> list[Tok]:
    if lang == "python":
        return _tokens_python(text, path)
    return _tokens_c_like(text, path, CPP_KW if lang == "cpp" else JAVA_KW)

# ---------------------------------------------------------------- отпечатки
def _h(s: str) -> int:
    return int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "big")

# файлы, которые обычно создаёт IDE: в сравнение не берём
IDE_FILES = {"stdafx.h", "stdafx.cpp", "pch.h", "pch.cpp", "framework.h", "targetver.h", "resource.h",
             "module-info.java", "__init__.py", "conftest.py", "setup.py", "manage.py"}

def fingerprints(toks: list[Tok], k: int = 5, window: int = 4) -> dict[int, list[int]]:
    """winnowing: хеш k-граммы -> список индексов начала k-граммы"""
    if len(toks) < k:
        return {}
    hashes = [_h(" ".join(t.kind for t in toks[i:i+k])) for i in range(len(toks) - k + 1)]
    fp: dict[int, list[int]] = {}
    last = -1
    for i in range(max(1, len(hashes) - window + 1)):
        win = hashes[i:i+window]
        j = i + min(range(len(win)), key=lambda x: (win[x], -x))
        if j != last:
            fp.setdefault(hashes[j], []).append(j)
            last = j
    return fp

def compare(a: list[Tok], b: list[Tok], k: int = 5, window: int = 4, exclude: set[int] | None = None) -> dict:
    """Сходство двух работ по токенам: процент и совпавшие строки в обеих.
    exclude: отпечатки шаблонного кода (выдан в задании), они не считаются совпадением."""
    fa, fb = fingerprints(a, k, window), fingerprints(b, k, window)
    if exclude:
        fa = {h: v for h, v in fa.items() if h not in exclude}
        fb = {h: v for h, v in fb.items() if h not in exclude}
    if not fa or not fb:
        return {"similarity": 0.0, "lines_a": {}, "lines_b": {}}
    common = fa.keys() & fb.keys()
    # доля общих отпечатков относительно меньшей работы (так копия части работы тоже видна)
    sim = len(common) / min(len(fa), len(fb))
    def lines(toks, fp):
        res: dict[str, set[int]] = {}
        for h in common:
            for i in fp[h]:
                for t in toks[i:i+k]:
                    res.setdefault(t.file, set()).add(t.line)
        return {f: sorted(v) for f, v in res.items()}
    return {"similarity": round(min(sim, 1.0), 4), "lines_a": lines(a, fa), "lines_b": lines(b, fb),
            "blocks": blocks(a, b, fa, fb, common, k, window)}

def blocks(a, b, fa, fb, common, k, window) -> list[dict]:
    """Склеивает совпавшие отпечатки в блоки: кусок кода у A и соответствующий ему кусок у B.
    Нужно, чтобы при просмотре пары было видно, какой фрагмент чему соответствует,
    даже если функции переставлены местами."""
    matches = [(i, j) for h in common for i in fa[h] for j in fb[h]]
    # 1) цепочки совпадений «по диагонали»: одинаковый сдвиг j - i (до 3 токенов), без больших разрывов
    by_off: dict[int, list[tuple[int, int]]] = {}
    for i, j in matches:
        by_off.setdefault(j - i, []).append((i, j))
    chains = []
    for off in sorted(by_off):
        for i, j in sorted(by_off[off]):
            for ch in chains[-8:]:
                pi, pj = ch[-1]
                if abs((j - i) - (pj - pi)) <= 3 and 0 <= i - pi <= k + window + 2:
                    ch.append((i, j)); break
            else:
                chains.append([(i, j)])
    # 2) жадный выбор: самые длинные цепочки, без повторного использования одних и тех же токенов
    chains.sort(key=lambda ch: -(ch[-1][0] - ch[0][0] + k))
    used_a: set[int] = set(); used_b: set[int] = set()
    groups = []
    for ch in chains:
        ra = set(range(ch[0][0], ch[-1][0] + k)); rb = set(range(min(j for _, j in ch), max(j for _, j in ch) + k))
        if len(ra & used_a) > len(ra) // 3 or len(rb & used_b) > len(rb) // 3:
            continue
        if len(ch) < 2 and len(ra) < k + 3:
            continue
        used_a |= ra; used_b |= rb
        groups.append(ch)
    out = []
    for g in groups:
        ta = [t for i, _ in g for t in a[i:i+k]]
        tb = [t for _, j in g for t in b[j:j+k]]
        def side(toks):
            d: dict[str, dict[int, int]] = {}
            for t in set(toks):              # сколько токенов блока стоит на каждой строке
                d.setdefault(t.file, {}).setdefault(t.line, 0)
                d[t.file][t.line] += 1
            f = max(d, key=lambda x: sum(d[x].values()))
            w = d[f]
            core = [ln for ln, c in w.items() if c >= 2] or list(w)
            return {"file": f, "lines": sorted(w), "w": {str(ln): c for ln, c in w.items()},
                    "first": min(core), "last": max(core)}
        A, B = side(ta), side(tb)
        if len(A["lines"]) >= 2 or len(g) >= 3:
            out.append({"a": A, "b": B})
    out.sort(key=lambda x: (x["a"]["file"], x["a"]["first"]))
    return out
