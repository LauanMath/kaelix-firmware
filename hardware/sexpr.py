"""Parser/serializador mínimo de s-expression do KiCad."""
import re

def tokenize(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t\r\n":
            i += 1
        elif c in "()":
            out.append(c); i += 1
        elif c == '"':
            j = i + 1; buf = []
            while j < n:
                if s[j] == "\\":
                    buf.append(s[j+1]); j += 2
                elif s[j] == '"':
                    break
                else:
                    buf.append(s[j]); j += 1
            out.append(('str', "".join(buf))); i = j + 1
        else:
            j = i
            while j < n and s[j] not in ' \t\r\n()"':
                j += 1
            out.append(('sym', s[i:j])); i = j
    return out

def parse(s):
    toks = tokenize(s); pos = 0
    def rd():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == "(":
            lst = []
            while toks[pos] != ")":
                lst.append(rd())
            pos += 1
            return lst
        return t
    forms = []
    while pos < len(toks):
        forms.append(rd())
    return forms

def dump(x, ind=0):
    pad = "\t" * ind
    if isinstance(x, tuple):
        if x[0] == 'str':
            v = x[1].replace("\\", "\\\\").replace('"', '\\"')
            return f'"{v}"'
        return x[1]
    if not x:
        return "()"
    head = dump(x[0])
    simple = all(not isinstance(e, list) for e in x)
    if simple:
        return "(" + " ".join(dump(e) for e in x) + ")"
    parts = [f"{pad}({head}"]
    for e in x[1:]:
        if isinstance(e, list):
            parts.append("\n" + dump(e, ind + 1))
        else:
            parts.append(" " + dump(e))
    parts.append("\n" + pad + ")")
    return "".join(parts)

def sym(name): return ('sym', name)
def st(v): return ('str', v)
def num(v): return ('sym', f"{v:g}" if isinstance(v, float) else str(v))
def head(form): return form[0][1] if form and isinstance(form[0], tuple) else None
def find(form, name):
    return [e for e in form if isinstance(e, list) and head(e) == name]
def find1(form, name):
    r = find(form, name)
    return r[0] if r else None
