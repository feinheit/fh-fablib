#!/usr/bin/env python3

"""
Extract strings::

    python3 extract_js_gettext_strings.py

Run tests::

    python3 -m doctest -v extract_js_gettext_strings.py

"""

import re
import subprocess
from collections import deque


def js_files():
    res = subprocess.run(
        ["git", "ls-files", "*.js", "*.mjs", "*.jsx", "*.ts", "*.tsx"],
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    return res.stdout.splitlines()


def strip_comments(source):
    """Remove JavaScript comments, leaving string literals alone

    >>> strip_comments("a // gettext('x')\\nb")
    'a \\nb'
    >>> strip_comments("a /* gettext('x') */ b")
    'a  b'
    >>> strip_comments('const url = "https://example.com" // nope')
    'const url = "https://example.com" '
    >>> strip_comments("gettext('a /* not a comment */ b')")
    "gettext('a /* not a comment */ b')"
    >>> strip_comments("gettext('it\\\\'s') // x")
    "gettext('it\\\\'s') "
    """
    out = []
    quote = ""
    idx = 0
    length = len(source)

    while idx < length:
        c = source[idx]

        if quote:
            out.append(c)
            if c == "\\" and idx + 1 < length:
                out.append(source[idx + 1])
                idx += 2
                continue
            if c == quote:
                quote = ""
            idx += 1
        elif c in {"'", '"', "`"}:
            quote = c
            out.append(c)
            idx += 1
        elif c == "/" and source[idx + 1 : idx + 2] == "/":
            while idx < length and source[idx] != "\n":
                idx += 1
        elif c == "/" and source[idx + 1 : idx + 2] == "*":
            end = source.find("*/", idx + 2)
            idx = length if end == -1 else end + 2
        else:
            out.append(c)
            idx += 1

    return "".join(out)


def extract_args(part):
    parens = 0
    quote = ""
    for idx, c in enumerate(part):
        if c == quote:
            quote = ""
        elif quote:
            pass
        elif c in {"'", '"', "`"}:
            quote = c
        elif c == "(":
            parens += 1
        elif c == ")":
            parens -= 1

        if parens == 0:
            return part[1:idx]

    return ""


def gettext_calls(source):
    """Extract *gettext calls from code

    >>> list(gettext_calls("gettext('abc')"))
    ["gettext('abc')"]
    >>> list(gettext_calls("abc def gettext('abc') xyz gettext blub"))
    ["gettext('abc')"]
    >>> list(gettext_calls("abc ngettext('singular', 'plural', someVar) def"))
    ["ngettext('singular', 'plural', someVar)"]
    >>> list(gettext_calls("abc def gettext ( ' abc ' ) xyz"))
    ["gettext(' abc ')"]
    >>> list(gettext_calls("gettext(':-/')"))
    ["gettext(':-/')"]
    >>> list(gettext_calls("gettext(':-)')"))
    ["gettext(':-)')"]
    >>> list(gettext_calls("abc gettext('xyz' def pgettext('ctx', 'str', ) xzz"))
    ["pgettext('ctx', 'str')"]
    >>> list(gettext_calls("gettext( 'Blub', )"))
    ["gettext('Blub')"]
    >>> list(gettext_calls("gettext(`Blub'`)"))
    ["gettext(`Blub'`)"]

    Calls inside comments are not calls:

    >>> list(gettext_calls("// gettext('nope')\\ngettext('yes')"))
    ["gettext('yes')"]
    >>> list(gettext_calls('''/**
    ...  * @example
    ...  * text: gettext(
    ...  *     "nope",
    ...  *   ),
    ...  */
    ... gettext("yes")'''))
    ['gettext("yes")']

    Neither are declarations, or calls which xgettext could not extract
    anyway because the first argument is not a literal string:

    >>> list(gettext_calls("declare function gettext(message: string): string"))
    []
    >>> list(gettext_calls("declare function ngettext(\\n  singular: string,\\n"
    ...                    "  plural: string,\\n  count: number,\\n): string"))
    []
    >>> list(gettext_calls("gettext(someVariable)"))
    []
    """

    parts = deque(
        part.strip() for part in re.split(r"\b(\w*gettext)\b", strip_comments(source))
    )

    while parts:
        top = parts.popleft()
        if not top.endswith("gettext"):
            continue

        if parts and (args := extract_args(parts.popleft())):
            args = args.strip().rstrip(",")
            # xgettext only ever sees literals, so anything else -- a variable,
            # or the parameter list of a TypeScript declaration -- is noise.
            if args[:1] in {"'", '"', "`"}:
                yield f"{top}({args})"


def generate_strings():
    calls = set()
    for file in js_files():
        with open(file, encoding="utf-8") as f:
            calls |= set(gettext_calls(f.read()))
    return sorted(calls, key=lambda c: (c.lower(), c))


if __name__ == "__main__":
    print(generate_strings())
